// One assembly as lipids in water, and the free molecules round it (src/lenses/lineage.js). The run
// says which type joins or leaves and in what order, the composition, each fission and how it divides
// the molecules: those the picture follows exactly, one lipid for each molecule. Everything else is the
// picture's own and no law of Cells computes it: how the lipids pack (a protocell, a closed shell of
// two faces, heads to the water outside and inside, tails between; a micelle, heads out and tails in;
// or loosely in a cluster), how they move, the paths by which a molecule comes in from the water and
// goes out into it, how the assembly lengthens, necks and parts, the gathering of the first assembly
// at a run's start, and the free molecules drifting in the water.
//
// What follows the run is BeadLayout's (src/lenses/assembly_beads.js): the same events, the same
// parting type by type. Here: where each lipid stands and which way it faces, and the stream of the
// run's joins and leaves (schema/ASSEMBLY_RUN.md, rule 4). At every speed the joins and leaves are
// seen: a joining molecule comes in from the water to its place, a leaving one goes out and away. So
// that the frame keeps its pace, no more than a cap are in flight at once: where a growth's pace would
// put more, one in N of its joins and leaves is drawn in flight (N from that growth's pace,
// `streamStride`), the others taking or leaving their places at once; the legend says N. A leaving
// molecule is no member from its event on: it goes on the leavers' list, never divided at a fission.
//
// Rule 4's one exception, said so on the picture: at a run's start the founder's molecules gather
// from the water, all at once, while the clock stands at the start. The run starts with the founder
// made, so the gathering is the picture's alone. With less motion asked for nothing gathers or flies.

import { BeadLayout } from "./assembly_beads.js";
import { HEAD, TAIL } from "./lipid_marks.js";

export const LIPID_FLIGHT_S = 0.9; // seconds a molecule takes to seep in from the water, or out into it, molecule by molecule
export const STREAM_FLIGHT_S = 1.15; // the same, at a speed of fissions a second
export const IN_FLIGHT_CAP = 4;    // molecules in flight at once, at most, molecule by molecule
/** Molecules in flight at once, at most, at a speed of fissions a second, wide and on a phone. */
export const STREAM_CAP = { wide: 26, narrow: 14 };
/**
 * The protocell's sizes, the picture's own (in the scene's units): a lipid's size against the
 * micelle's, the two faces' distance apart, the tails' length, its outer radius at no molecules and
 * what it gains up to the fission size (80), and the share of molecules in the outer face. Worked
 * out at 40 molecules (a daughter) and at 80: about a fifth to a quarter of each face is heads, and
 * the inside's clear radius is 0.4 to 0.8, where the catalytic network is drawn.
 */
export const PROTOCELL = { head: 1.2, thickness: 0.72, tail: 0.24, base: 1.05, grow: 0.75, outer: 0.76 };

/** One in how many of a growth's joins and leaves is drawn in flight, so that no more than `cap` fly at once. */
export function streamStride({ eventsPerSecond, cap, flight = STREAM_FLIGHT_S }) {
  return Math.max(1, Math.ceil((Math.max(0, eventsPerSecond) * flight) / Math.max(1, cap)));
}
export const GATHER_S = 3.6;       // seconds the founder takes to gather, all told
export const ADRIFT_S = 2.2;       // seconds the daughter let go takes to drift off into the haze
/** Free molecules in the water, wide and on a phone: their number is the picture's, their mix the run's supply. */
export const CROWD = { wide: 96, narrow: 36 };

const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const norm = (v) => { const l = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / l, v[1] / l, v[2] / l]; };

/** A smooth union of two balls (a polynomial smooth minimum): its value and its gradient at p (into `out`, where given). */
export function neckField(p, balls, k, out = { f: 0, g: [0, 0, 0] }) {
  const a = balls[0];
  const ax = p[0] - a.c[0], ay = p[1] - a.c[1], az = p[2] - a.c[2], al = Math.hypot(ax, ay, az) || 1e-9, af = al - a.r;
  if (balls.length === 1 || !(k > 0)) {
    out.f = af; out.g[0] = ax / al; out.g[1] = ay / al; out.g[2] = az / al;
    return out;
  }
  const b = balls[1];
  const bx = p[0] - b.c[0], by = p[1] - b.c[1], bz = p[2] - b.c[2], bl = Math.hypot(bx, by, bz) || 1e-9, bf = bl - b.r;
  const h = Math.min(1, Math.max(0, 0.5 + (0.5 * (bf - af)) / k));
  out.f = bf * (1 - h) + af * h - k * h * (1 - h);
  const gx = (ax / al) * h + (bx / bl) * (1 - h), gy = (ay / al) * h + (by / bl) * (1 - h), gz = (az / al) * h + (bz / bl) * (1 - h);
  const gl = Math.hypot(gx, gy, gz) || 1;
  out.g[0] = gx / gl; out.g[1] = gy / gl; out.g[2] = gz / gl;
  return out;
}

/**
 * Where a ray from `from` along `dir` first leaves the field's surface, and the surface's normal
 * there: stepped out to the first point outside, then halved down to it (a ray may pass out of one
 * ball and into the other).
 */
export function surfaceAlong(from, dir, balls, k, reach) {
  const at = [0, 0, 0], field = { f: 0, g: [0, 0, 0] };
  const f = (t) => {
    at[0] = from[0] + dir[0] * t; at[1] = from[1] + dir[1] * t; at[2] = from[2] + dir[2] * t;
    return neckField(at, balls, k, field).f;
  };
  const step = Math.max(0.02, reach / 24);
  let lo = 0, hi = -1;
  for (let t = step; t <= reach + 1e-9; t += step) {
    if (f(t) >= 0) { hi = t; break; }
    lo = t;
  }
  if (hi < 0) return null; // nothing outside within reach: the ray runs on into the other ball
  for (let i = 0; i < 10; i++) {
    const mid = (lo + hi) / 2;
    if (f(mid) < 0) lo = mid; else hi = mid;
  }
  f((lo + hi) / 2);
  return { point: at.slice(), normal: field.g.slice() };
}
const sub3 = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
/** Where the run's joins come in from and its leaves go out to, by the parting's axis: across (0), or up and down (1). */
const STREAM_IN = [[-1, 0.12, 0.3], [-0.45, -1, 0.15]];
const STREAM_OUT = [[1, 0.12, 0.3], [0.45, -1, 0.15]];
const dot3 = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

export class LipidLayout extends BeadLayout {
  constructor(options = {}) {
    super(options);
    this.gathering = false;
    this.adrift = []; // the daughter let go, drifting off: lipids with their own clock
    this.leavers = []; // molecules that have left, going out into the water: no members of the assembly
    this.drawn = [];
    this.stride = 1; // one in so many joins and leaves is drawn in flight
    this.flightCap = IN_FLIGHT_CAP;
    this.flightSpan = LIPID_FLIGHT_S;
    this.eventIndex = 0;
  }

  /**
   * A molecule joins or leaves, as the run says. A join is a member at once, drawn coming in from the
   * water where it is one of the stride's; a leave is no member from its event, drawn going out where
   * it is one of the stride's.
   */
  apply(event) {
    const type = Math.abs(event) - 1;
    const shown = this.mode === "flight" && this.eventIndex++ % Math.max(1, this.stride) === 0;
    if (event > 0) {
      const bead = this.bead(type, shown);
      bead.span = this.flightSpan;
      this.beads.push(bead);
      return;
    }
    let index = -1;
    for (let i = this.beads.length - 1; i >= 0; i--) {
      if (this.beads[i].type !== type) continue;
      index = i;
      if (this.beads[i].flight >= 1) break; // one in its place leaves first
    }
    if (index < 0) return;
    const [bead] = this.beads.splice(index, 1);
    if (shown && bead.pos) this.leavers.push({ ...bead, leaving: true, flight: 0, wait: 0, span: this.flightSpan, start: bead.pos.slice(), axis: (bead.axis || bead.dir).slice(), centre: this.centres[bead.side].slice(), r: this.radius(this.counts[bead.side] || 1) });
  }

  bead(type, arriving) {
    const bead = super.bead(type, arriving);
    bead.phase = this.random() * 6.2831;
    bead.spin = this.random() * 6.2831;
    bead.loose = norm([this.random() * 2 - 1, this.random() * 2 - 1, this.random() * 2 - 1]);
    bead.wander = norm([this.random() * 2 - 1, this.random() * 1.2 - 0.5, this.random() * 2 - 1]);
    bead.wait = 0;
    bead.span = LIPID_FLIGHT_S;
    bead.leaflet = this.random() < PROTOCELL.outer ? 0 : 1; // in a protocell, its face: the outer (0) or the inner (1)
    return bead;
  }

  /** A ball whose surface holds as many heads as it has molecules (the picture's choice): a protocell's outer face, a micelle packed close, a loose cluster. */
  radius(count) {
    if (this.shape === "protocell") return PROTOCELL.base + PROTOCELL.grow * (count / 80);
    return this.shape === "cluster" ? 0.95 * Math.cbrt(count / 80) : 0.84 * Math.sqrt(count / 80);
  }

  /** How large a lipid in its place is drawn, against the micelle's. */
  get lipidScale() {
    return this.shape === "protocell" ? PROTOCELL.head : 1;
  }

  /** The founder's molecules, scattered in the water, gather into the first assembly. */
  gather() {
    this.gathering = true;
    for (const bead of this.beads) {
      bead.flight = 0;
      bead.leaving = false;
      bead.glow = 0;
      bead.span = GATHER_S * (0.45 + 0.25 * this.random());
      bead.wait = (GATHER_S - bead.span) * this.random();
      bead.from = null;
      bead.reach = 1.4 + 2.6 * this.random();
    }
  }

  /** As BeadLayout follows the run; the daughter let go at a fission is kept a while, drifting off. */
  follow(run, phase) {
    const last = this.at;
    const fromSplit = last && last.phase === "split" && phase.phase === "grow" && phase.g === last.k && phase.e <= 240;
    if (fromSplit && this.mode !== "still") {
      const other = this.beads.filter((bead) => bead.side === 1 && !bead.gone && bead.pos);
      this.adrift = other.map((bead) => ({ ...bead, pos: bead.pos.slice(), axis: (bead.axis || bead.dir).slice(), left: ADRIFT_S, start: bead.pos.slice() }));
    } else if (!fromSplit && !(last && last.phase === phase.phase && (last.g === phase.g || last.k === phase.k))) {
      this.adrift = [];
    }
    const rebuilt = super.follow(run, phase);
    if (rebuilt) { this.adrift = []; this.leavers = []; this.gathering = false; }
    // The daughters part more slowly than BeadLayout's (so the neck shows), and the one let go drifts back into the haze.
    if (phase.phase === "split") {
      const s = phase.part, d = this.radius(40) * 1.25, apart = smooth(0, 0.72, s), back = smooth(0.72, 1, s);
      const along = (amount) => (this.axis === 1 ? [0, amount, 0] : [amount, 0, 0]);
      const keep = along(-d * apart * (1 - back)), go = along(d * apart * (1 + 0.5 * back));
      const deep = this.shape === "protocell" ? 6 : 3; // back into the haze, by the assembly's size
      this.centres = [keep, [go[0], go[1] + 0.3 * back, go[2] - deep * back]];
      this.fade = back;
      this.split = s;
    }
    return rebuilt;
  }

  /** Divide the molecules as the run records, type by type; of each type, those on the parting's near side go to the daughter that carries on. */
  part(run, k) {
    const keep = Int32Array.from(run.carried(k));
    this.beads = this.beads.filter((bead) => !bead.gone);
    const along = (bead) => (this.axis === 1 ? bead.dir[1] : bead.dir[0]);
    const order = this.beads.slice().sort((a, b) => along(a) - along(b));
    for (const bead of order) {
      if (keep[bead.type] > 0) { keep[bead.type]--; bead.side = 0; } else bead.side = 1;
    }
    // Each daughter's molecules spread evenly over all of its own ball at once (place() presses them to its end while the
    // two overlap), so that the daughter that carries on is whole when they part.
    for (const side of [0, 1]) this.spread(this.beads.filter((bead) => bead.side === side));
  }

  /** Even directions for these molecules (a Fibonacci sphere), each taking the free one nearest its own. */
  spread(beads) {
    const n = beads.length;
    if (n < 2) return;
    const free = [];
    for (let i = 0; i < n; i++) {
      const y = 1 - (2 * (i + 0.5)) / n, r = Math.sqrt(Math.max(0, 1 - y * y)), a = i * 2.399963229728653;
      free.push([Math.cos(a) * r, y, Math.sin(a) * r]);
    }
    for (const bead of beads) {
      let best = 0, near = -2;
      for (let i = 0; i < free.length; i++) {
        const d = free[i][0] * bead.dir[0] + free[i][1] * bead.dir[1] + free[i][2] * bead.dir[2];
        if (d > near) { near = d; best = i; }
      }
      bead.dir = free.splice(best, 1)[0];
    }
  }

  /**
   * Where a lipid of a side stands now, and which way its head faces: on the assembly's surface, or
   * loosely in its ball. While the two daughters overlap, each one's molecules keep to the part of
   * its ball outside the other (their directions pressed away from the other, so far as the circle
   * where the two balls meet), and the smooth union of the two balls draws the neck between them.
   */
  place(bead, balls, k, splitting) {
    // A protocell's inner face stands on the same shape drawn in by the faces' distance apart, its heads turned in.
    const inner = this.shape === "protocell" && bead.leaflet === 1;
    if (inner) balls = balls.map((ball) => ({ c: ball.c, r: Math.max(0.25, ball.r - PROTOCELL.thickness) }));
    const placed = this.placeOn(bead, balls, k, splitting);
    if (this.shape === "protocell") placed.tail = PROTOCELL.tail;
    if (inner) placed.normal = placed.normal.map((x) => -x);
    return placed;
  }

  placeOn(bead, balls, k, splitting) {
    const side = bead.side, own = balls[side] || balls[0];
    if (this.shape === "cluster") {
      const r = own.r * (0.35 + 0.65 * bead.depth);
      return { point: [0, 1, 2].map((a) => own.c[a] + bead.dir[a] * r), normal: bead.loose, inner: own.r };
    }
    let dir = bead.dir, origin = own.c;
    if (splitting) {
      const other = balls[1 - side];
      const v = [other.c[0] - own.c[0], other.c[1] - own.c[1], other.c[2] - own.c[2]];
      const gap = Math.hypot(v[0], v[1], v[2]);
      if (gap > 1e-6 && gap < own.r + other.r) {
        const u = v.map((x) => x / gap);
        const meet = Math.acos(Math.min(1, Math.max(-1, (gap * gap + own.r * own.r - other.r * other.r) / (2 * gap * own.r))));
        const cos = Math.min(1, Math.max(-1, dir[0] * u[0] + dir[1] * u[1] + dir[2] * u[2]));
        let w = [dir[0] - u[0] * cos, dir[1] - u[1] * cos, dir[2] - u[2] * cos];
        const wl = Math.hypot(w[0], w[1], w[2]);
        w = wl > 1e-6 ? w.map((x) => x / wl) : Math.abs(u[1]) < 0.9 ? norm([u[2], 0, -u[0]]) : norm([0, u[2], -u[1]]);
        // Spread evenly (by area) over this daughter's own part of its ball, from the circle where the two meet to its far pole.
        const area = (1 - cos) / 2, top = Math.cos(meet);
        const pressed = Math.acos(Math.min(1, Math.max(-1, top - area * (top + 1))));
        dir = [0, 1, 2].map((a) => u[a] * Math.cos(pressed) + w[a] * Math.sin(pressed));
      }
    }
    const pair = splitting ? [own, balls[1 - side]] : [own];
    let hit = surfaceAlong(origin, dir, pair, k, own.r * 1.25 + k);
    // Where the ray runs on into the other daughter (near the neck, where the two blend), it is turned away from the other until it leaves on its own side.
    if (!hit && splitting) {
      const away = norm(sub3(own.c, balls[1 - side].c));
      for (let turn = 1; turn <= 10 && !hit; turn++) {
        dir = norm([0, 1, 2].map((a) => dir[a] + away[a] * 0.2));
        hit = surfaceAlong(origin, dir, pair, k, own.r * 1.25 + k);
      }
    }
    if (!hit) {
      const point = [0, 1, 2].map((a) => own.c[a] + dir[a] * own.r);
      return { point, normal: dir, inner: own.r };
    }
    return { point: hit.point, normal: hit.normal, inner: own.r };
  }

  /** Move each lipid toward its place; returns whether anything still moves. */
  step(seconds, { still = false } = {}) {
    this.relax(still ? 0 : 1);
    const ease = still || !seconds ? 1 : 1 - Math.exp(-seconds * 7);
    const splitting = this.split > 0 && this.split < 1;
    const balls = [0, 1].map((side) => ({ c: this.centres[side], r: this.radius(this.counts[side] || 1) }));
    const k = 0.42 * Math.max(balls[0].r, 0.5);
    let moving = false, glowing = 0, flying = 0;
    const big = this.lipidScale;
    for (const bead of this.beads) {
      const placed = this.place(bead, balls, k, splitting);
      const { point, normal, inner } = placed;
      // The head sits just out of the surface; the tails reach inward, as long as the assembly is deep (a protocell's to the middle of its two faces).
      const target = [0, 1, 2].map((a) => point[a] + normal[a] * HEAD * 0.15 * big);
      const tail = placed.tail ?? (this.shape === "cluster" ? 0.5 : Math.min(TAIL.longest, TAIL.share * inner));
      if (still) { bead.flight = 1; bead.wait = 0; }
      if (bead.flight < 1) {
        if (bead.wait > 0) bead.wait = Math.max(0, bead.wait - seconds);
        else bead.flight = Math.min(1, bead.flight + seconds / (bead.span || LIPID_FLIGHT_S));
        moving = true;
      }
      if (bead.flight < 1 && !bead.from) {
        // From the water round it, and from the far side more than the near (the camera first looks from the front).
        // A join of the run comes in from one side (the left; from below on a tall screen), as the leaves go out on the other.
        const c = balls[bead.side].c, reach = bead.reach || 3.4;
        const w = this.gathering ? norm([0, 1, 2].map((a) => bead.dir[a] * 0.6 + bead.wander[a])) : norm([0, 1, 2].map((a) => bead.dir[a] * 0.35 + STREAM_IN[this.axis][a] + bead.wander[a] * 0.4));
        w[2] = Math.min(w[2], 0.25);
        // On a tall screen (the daughters part up and down) the frame is narrow and the page's card stands above: a molecule comes from below, inside the frame.
        const spread = this.axis === 1 ? [0.38, 1.1, 0.7] : [1, 1, 1];
        if (this.axis === 1) w[1] = -0.35 - 0.65 * Math.abs(w[1]);
        bead.from = [0, 1, 2].map((a) => c[a] + w[a] * (balls[bead.side].r + reach) * spread[a]);
      }
      let pos = target, axis = normal, flex = 0.35;
      if (bead.flight < 1) {
        {
          // In from the water: a drift that slows as it comes near, then the lipid turns tails-in and settles.
          const f = smooth(0, 1, bead.flight), g = 1 - f;
          const ctrl = [0, 1, 2].map((a) => target[a] + normal[a] * 1.1 + bead.wander[a] * 0.8);
          pos = [0, 1, 2].map((a) => g * g * bead.from[a] + 2 * g * f * ctrl[a] + f * f * target[a]);
          const turn = smooth(0.55, 1, bead.flight);
          axis = norm([0, 1, 2].map((a) => bead.loose[a] * (1 - turn) + normal[a] * turn));
          flex = 1.45 - 1.1 * turn;
          bead.scale = 1 + (big - 1) * turn;
        }
        flying++;
      } else {
        // In its place: it eases there, as the assembly grows, necks and parts.
        bead.scale = big;
        const from = bead.pos || target;
        for (let a = 0; a < 3; a++) if (Math.abs(target[a] - from[a]) > 1e-4) moving = true;
        pos = [0, 1, 2].map((a) => from[a] + (target[a] - from[a]) * ease);
        if (bead.axis) axis = norm([0, 1, 2].map((a) => bead.axis[a] + (normal[a] - bead.axis[a]) * ease));
      }
      bead.pos = pos;
      bead.axis = axis;
      bead.tailLength = tail;
      bead.flex = flex;
      if (bead.glow > 0) {
        bead.glow = still ? 0 : Math.max(0, bead.glow - seconds);
        if (bead.glow > 0) { glowing++; moving = true; }
      }
    }
    if (this.gathering && !this.beads.some((bead) => bead.flight < 1)) this.gathering = false;
    this.beads = this.beads.filter((bead) => !bead.gone);
    // The molecules that left go out into the water, to the other side from the joins, and are gone.
    for (const bead of this.leavers) {
      if (still) bead.flight = 1;
      else bead.flight = Math.min(1, bead.flight + seconds / (bead.span || LIPID_FLIGHT_S));
      const f = smooth(0, 1, bead.flight);
      const out = norm([0, 1, 2].map((a) => bead.dir[a] * 0.35 + STREAM_OUT[this.axis][a] + bead.wander[a] * 0.4));
      const spread = this.axis === 1 ? [0.45, 1.1, 0.8] : [1, 1, 1];
      const far = [0, 1, 2].map((a) => bead.centre[a] + out[a] * (bead.r + 4.2) * spread[a]);
      bead.pos = [0, 1, 2].map((a) => bead.start[a] + (far[a] - bead.start[a]) * f);
      bead.axis = norm([0, 1, 2].map((a) => bead.axis[a] * (1 - 0.15 * f) + bead.loose[a] * 0.15 * f));
      bead.flex = 0.35 + 1.1 * f;
      bead.scale = (1 + (big - 1) * (1 - smooth(0, 0.5, bead.flight))) * (1 - 0.35 * smooth(0.6, 1, bead.flight));
      if (bead.flight < 1) { flying++; moving = true; }
    }
    this.leavers = this.leavers.filter((bead) => bead.flight < 1);
    // No more in flight than the cap: the oldest arrive (or are gone) first (the gathering aside).
    if (!this.gathering && flying > this.flightCap) {
      const flown = [...this.beads.filter((bead) => bead.flight < 1), ...this.leavers].sort((a, b) => b.flight - a.flight);
      for (const bead of flown.slice(0, flying - this.flightCap)) bead.flight = 1;
      this.leavers = this.leavers.filter((bead) => bead.flight < 1);
    }
    if (glowing > 10) {
      const lit = this.beads.filter((bead) => bead.glow > 0).sort((a, b) => a.glow - b.glow);
      for (const bead of lit.slice(0, glowing - 10)) bead.glow = 0;
    }
    // The daughter let go drifts on into the haze, and is gone.
    for (const bead of this.adrift) {
      bead.left = still ? 0 : Math.max(0, bead.left - seconds);
      const f = 1 - bead.left / ADRIFT_S;
      // Off into the haze, by the assembly's size (a protocell is larger than the micelle).
      const size = this.shape === "protocell" ? 2 : 1;
      const d = [this.axis === 1 ? 0 : 0.5 * size, this.axis === 1 ? 0.8 * size : 0.5, -4.5 * size * size];
      bead.pos = [0, 1, 2].map((a) => bead.start[a] + d[a] * smooth(0, 1, f));
      bead.fade = 0.75 + 0.25 * f;
      if (bead.left > 0) moving = true;
    }
    this.adrift = this.adrift.filter((bead) => bead.left > 0);
    return moving;
  }

  /** How many lipids are in flight (coming in or going out), and how many glow (the gathering's included). */
  inMotion() {
    let flying = this.leavers.length, glowing = 0;
    for (const bead of this.beads) {
      if (bead.flight < 1) flying++;
      if (bead.glow > 0) glowing++;
    }
    return { flying, glowing };
  }

  /** The members, type by type (a molecule in flight to its place is a member; one that has left is not). */
  members(n) {
    const x = new Int32Array(n);
    for (const bead of this.beads) if (!bead.gone) x[bead.type]++;
    return x;
  }
}

/** A small stream of numbers that is the same everywhere. */
function stream(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * The free molecules in the water round the assembly: the run's supply, which it holds fixed, drawn
 * as so many lipids drifting. Their mix of types follows the supply the run states (every type alike
 * where it holds every type at one concentration); their number, places and motion are the
 * picture's. Where each one stands is a function of the water's clock alone; none stands between the
 * camera and the assembly.
 */
export class FreeCrowd {
  constructor(environment, { seed = 77, narrow = false } = {}) {
    const random = stream(seed);
    const n = environment.count;
    const weights = environment.raw?.reservoir?.by_type || null;
    const total = weights ? weights.reduce((a, b) => a + b, 0) : n;
    const pickType = () => {
      if (!weights) return Math.floor(random() * n) % n;
      let x = random() * total;
      for (let i = 0; i < n; i++) { x -= weights[i]; if (x <= 0) return i; }
      return n - 1;
    };
    this.all = [];
    for (let i = 0; i < CROWD.wide; i++) {
      const theta = random() * Math.PI * 2, y = random() * 1.5 - 0.7, r = 3.2 + Math.pow(random(), 0.7) * 9;
      const s = Math.sqrt(Math.max(0, 1 - y * y));
      this.all.push({
        type: pickType(),
        base: [Math.cos(theta) * s * r, y * r * 0.7, Math.sin(theta) * s * r],
        w: [0.05 + random() * 0.08, 0.04 + random() * 0.06, 0.05 + random() * 0.08],
        p: [random() * 6.28, random() * 6.28, random() * 6.28, random() * 6.28, random() * 6.28, random() * 6.28],
        a: 0.35 + random() * 0.55,
        phase: random() * 6.28,
        spin: random() * 6.28,
      });
    }
    this.setNarrow(narrow);
  }

  setNarrow(narrow) {
    this.count = narrow ? CROWD.narrow : CROWD.wide;
  }

  /**
   * Each free molecule's place and facing at the water's clock, round `centre`, kept clear of the
   * line from `eye` (the camera) to the assembly: [{ type, pos, axis, phase, spin }].
   */
  at(time, centre = [0, 0, 0], eye = null) {
    const out = [];
    let toEye = null, length = 0;
    if (eye) {
      const v = [eye[0] - centre[0], eye[1] - centre[1], eye[2] - centre[2]];
      length = Math.hypot(v[0], v[1], v[2]);
      toEye = length > 1e-6 ? v.map((x) => x / length) : null;
    }
    for (let i = 0; i < this.count; i++) {
      const m = this.all[i];
      const p = [
        m.base[0] + Math.sin(time * m.w[0] + m.p[0]) * m.a,
        m.base[1] + Math.sin(time * m.w[1] + m.p[1]) * m.a * 0.6,
        m.base[2] + Math.cos(time * m.w[2] + m.p[2]) * m.a,
      ];
      if (toEye) {
        const along = p[0] * toEye[0] + p[1] * toEye[1] + p[2] * toEye[2];
        if (along > 0 && along < length) {
          const side = [p[0] - along * toEye[0], p[1] - along * toEye[1], p[2] - along * toEye[2]];
          const off = Math.hypot(side[0], side[1], side[2]);
          // clear of the assembly's line of sight, and never near the camera's own place
          const clear = 1.9 + 1.6 * Math.max(0, along - length * 0.5) / (length * 0.5);
          if (off < clear) {
            const s = off > 1e-6 ? side.map((x) => x / off) : [1, 0, 0];
            for (let a = 0; a < 3; a++) p[a] += s[a] * (clear - off);
          }
        }
      }
      const axis = norm([Math.sin(time * 0.21 + m.p[3]), Math.cos(time * 0.17 + m.p[4]), Math.sin(time * 0.13 + m.p[5])]);
      out.push({ type: m.type, pos: [p[0] + centre[0], p[1] + centre[1], p[2] + centre[2]], axis, phase: m.phase, spin: m.spin + time * 0.1 });
    }
    return out;
  }
}
