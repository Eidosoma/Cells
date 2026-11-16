// A readout for judging the resting look on the device in the visitor's hand. It is shown
// only when the address asks for it ("fps=1"), in a view that wears the rich look. The
// server that checks this page draws in software, so nothing measured there says what a
// graphics card will do: the frame rate that counts is the one read here.
//
// It shows how long a frame takes, what was drawn, and a switch for each of the seven
// effects (core/look.js). Switching one by hand rests the device's own fallback, since the
// visitor is then the judge; choosing the look again on the card starts it afresh.
//
// The readout carries its own few rules of style, so that it adds nothing to the page's.

import { EFFECTS, STEPS } from "./look.js";

const STYLE = `
.look-trial { position: absolute; right: max(16px, env(safe-area-inset-right, 0px)); top: 64px; z-index: 5; width: 280px; max-width: calc(100% - 32px);
  padding: 9px 12px 10px; border-radius: 12px; border: 1px solid var(--line); background: var(--bg-raised); color: var(--fg);
  font: 12px/1.35 var(--font-body, system-ui, sans-serif); box-shadow: 0 6px 22px rgb(0 0 0 / 0.1); }
.has-panel .look-trial { right: calc(max(16px, env(safe-area-inset-right, 0px)) + 376px); }
.look-trial .switches { display: grid; grid-template-columns: 1fr 1fr; gap: 0 10px; }
.look-trial h3 { margin: 0 0 6px; font: 600 11px/1.2 var(--font-display, system-ui, sans-serif); letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }
.look-trial .rate { font-variant-numeric: tabular-nums; font-size: 13px; margin: 0 0 2px; }
.look-trial .drawn { font-variant-numeric: tabular-nums; color: var(--muted); margin: 0 0 6px; }
.look-trial label { display: flex; align-items: center; gap: 7px; padding: 2px 0; cursor: pointer; }
.look-trial input { margin: 0; accent-color: var(--accent); }
.look-trial .says { margin: 6px 0 0; color: var(--muted); }
@media (max-width: 760px) { .look-trial, .has-panel .look-trial { top: auto; right: max(12px, env(safe-area-inset-right, 0px)); bottom: calc(200px + env(safe-area-inset-bottom, 0px)); } }
`;

const el = (name, props = {}, ...children) => {
  const node = Object.assign(document.createElement(name), props);
  node.append(...children);
  return node;
};

export class LookTrial {
  constructor(stage) {
    this.stage = stage;
    this.times = [];
    this.last = 0;
    this.rate = el("p", { className: "rate" }, "Frame: measuring");
    this.drawn = el("p", { className: "drawn" });
    this.says = el("p", { className: "says" });
    this.boxes = new Map();
    const switches = EFFECTS.map((effect) => {
      const box = el("input", { type: "checkbox" });
      box.dataset.effect = effect.id;
      box.addEventListener("change", () => this.stage.look.set(effect.id, box.checked));
      this.boxes.set(effect.id, box);
      return el("label", { title: `What a frame pays for it: ${effect.cost}.` }, box, effect.label);
    });
    this.box = el("div", { className: "look-trial" }, el("style", {}, STYLE), el("h3", {}, "The look, on this device"), this.rate, this.drawn, el("div", { className: "switches" }, ...switches), this.says);
    this.box.setAttribute("role", "group");
    this.box.setAttribute("aria-label", "The look, tried on this device");
    this.onFrame = () => this.frame();
    this.stop = null;
    this.timer = null;
  }

  show() {
    if (this.box.isConnected) return;
    (this.stage.canvas.parentNode || this.stage.host.shadowRoot || this.stage.host).append(this.box);
    this.stage.afterRender.add(this.onFrame);
    this.stop = this.stage.look.onChange(() => this.sync());
    this.timer = setInterval(() => this.write(), 500);
    this.sync();
    this.write();
  }

  hide() {
    this.box.remove();
    this.stage.afterRender.delete(this.onFrame);
    this.stop?.();
    this.stop = null;
    clearInterval(this.timer);
    this.timer = null;
    this.times.length = 0;
    this.last = 0;
  }

  /** A frame was drawn: keep how long it came after the one before, while the picture moves and frames follow one another. */
  frame() {
    const now = performance.now();
    if (this.last && this.stage.moving) this.times.push(now - this.last);
    else this.times.length = 0; // the picture stood still in between
    if (this.times.length > 60) this.times.shift();
    this.last = now;
  }

  write() {
    const still = !this.stage.running || !this.times.length;
    if (still) this.rate.textContent = "Frame: the picture is still";
    else {
      const mean = this.times.reduce((sum, value) => sum + value, 0) / this.times.length;
      this.rate.textContent = `Frame: ${mean.toFixed(1)} ms · ${(1000 / mean).toFixed(mean > 100 ? 1 : 0)} a second`;
    }
    const info = this.stage.renderer.info.render;
    this.drawn.textContent = `${info.calls} draws · ${info.triangles.toLocaleString("en-US")} triangles`;
  }

  /** The switches and the words follow the look as it now is. */
  sync() {
    const look = this.stage.look;
    for (const [id, box] of this.boxes) {
      box.checked = look.on(id);
      box.disabled = !look.rich;
    }
    const words = [];
    if (!look.rich) words.push("The look is plain: choose Rich on the card to try the effects.");
    else if (look.held) words.push("Every switch stays as set: the device's own fallback rests while you judge.");
    else if (look.step) words.push(`This device stepped down: ${STEPS[look.step].id}.`);
    else words.push("If a moving picture stays under 25 frames a second, the device gives up contact shade first, then the rest.");
    if (look.rich && this.stage.decoration.still) words.push("The drift and the shimmer are still: this device asks for less motion.");
    else if (look.rich && !this.stage.decoration.moving) words.push("The drift and the shimmer are held still while something else moves.");
    this.says.textContent = words.join(" ");
  }

  dispose() {
    this.hide();
  }
}
