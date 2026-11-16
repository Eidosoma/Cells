// <cells-timeline>: the playhead of a replay. Play and pause, drag or step through the
// run, change the speed. Ticks mark each event of the run, a flag marks the judged
// record, and the read-out gives the time in plain units.
//
// It is bound to a Player (src/replay/player.js) and only moves the playhead: what the
// run looked like at that time is drawn by the lens. The playhead is the replay's one
// clock: the beads of a layer that moves keep its time, so its speed is theirs.
//
// The speed: a button that says the speed shown ("60×", "1/1,000×") opens the steps the
// run is offered, slower and faster than true speed, each with what one second of watching
// is in the run. A step pressed is taken and the list closes; Escape closes it too.
//
// Keys, with the slider in focus: Left and Right step one saved record, Page Up and
// Page Down jump to the next event, Home and End go to the ends, Space plays or pauses,
// < and > take the next slower or faster speed.

import { h, svg } from "./dom.js";
import { clock, duration } from "../replay/format.js";
import { SPEEDS, speedWords } from "../replay/player.js";

const PLAY = "M7 4.5v15l12-7.5z", PAUSE = "M6.5 4.5h4v15h-4zM13.5 4.5h4v15h-4z";

class CellsTimeline extends HTMLElement {
  connectedCallback() {
    if (this.built) return;
    this.built = true;
    this.icon = svg("path", { d: PLAY });
    this.playButton = h("button", { class: "tl-play", type: "button", onclick: () => this.player?.toggle() }, svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" }, this.icon));
    this.marks = svg("svg", { class: "tl-marks", viewBox: "0 0 1000 24", preserveAspectRatio: "none", "aria-hidden": "true" });
    this.fill = h("div", { class: "tl-fill" });
    this.flag = h("span", { class: "tl-flag", hidden: true }, "judged");
    this.range = h("input", { id: "cells-timeline-range", class: "tl-range", type: "range", step: "any", "aria-label": "Time in the run" });
    this.now = h("b", {});
    this.rest = h("span", {});
    this.speedButton = h("button", { class: "tl-speed", type: "button", "aria-haspopup": "true", "aria-expanded": "false", "aria-controls": "cells-timeline-speeds", onclick: () => this.showSpeeds(this.speedList.hidden) });
    this.speedList = h("div", { id: "cells-timeline-speeds", class: "tl-speeds", role: "group", "aria-label": "Speed of the replay", hidden: true });
    this.append(
      this.playButton,
      h("div", { class: "tl-body" }, h("div", { class: "tl-track" }, h("div", { class: "tl-rail" }, this.fill), this.marks, this.flag, this.range), h("p", { class: "tl-read" }, this.now, this.rest)),
      this.speedButton,
      this.speedList
    );
    // The list of speeds closes with Escape, and with a press anywhere else.
    this.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || this.speedList.hidden) return;
      this.showSpeeds(false);
      this.speedButton.focus();
      event.stopPropagation();
    });
    this.closeSpeeds = (event) => {
      if (!this.speedList.hidden && !event.composedPath().includes(this)) this.showSpeeds(false);
    };

    // While the slider is held, the run does not play on underneath it.
    let resume = false;
    this.range.addEventListener("pointerdown", () => {
      resume = Boolean(this.player?.playing);
      this.player?.pause();
    });
    this.range.addEventListener("input", () => this.player?.seek(Number(this.range.value)));
    this.range.addEventListener("change", () => {
      if (resume) this.player?.play();
      resume = false;
    });
    this.range.addEventListener("keydown", (event) => {
      const player = this.player;
      if (!player?.run) return;
      if (event.key === "ArrowLeft" || event.key === "ArrowDown") player.step(-1);
      else if (event.key === "ArrowRight" || event.key === "ArrowUp") player.step(1);
      else if (event.key === "Home") player.seek(player.start);
      else if (event.key === "End") player.seek(player.end);
      else if (event.key === "PageDown" || event.key === "PageUp") this.toEvent(event.key === "PageDown" ? 1 : -1);
      else if (event.key === " " || event.key === "Enter") player.toggle();
      else if (event.key === "<" || event.key === ">") this.stepSpeed(event.key === ">" ? 1 : -1);
      else return;
      event.preventDefault();
    });
    if (this.player) this.sync();
  }

  disconnectedCallback() {
    this.showSpeeds(false);
    this.unbind();
  }

  /** Follow a player. `words` names the run's events ("replacement"). */
  bind(player, { eventWord = "event" } = {}) {
    if (this.player === player && this.eventWord === eventWord && this.run === player.run) return;
    this.unbind();
    this.player = player;
    this.eventWord = eventWord;
    this.onTime = () => this.place();
    this.onState = () => this.sync();
    player.addEventListener("time", this.onTime);
    player.addEventListener("state", this.onState);
    if (this.built) this.sync();
  }

  unbind() {
    this.player?.removeEventListener("time", this.onTime);
    this.player?.removeEventListener("state", this.onState);
    this.player = null;
  }

  /** Everything that changes when the run, the speed or playing changes. */
  sync() {
    const player = this.player;
    if (!player || !this.built) return;
    const run = player.run;
    if (run !== this.run) {
      this.run = run;
      this.range.min = String(player.start);
      this.range.max = String(player.end);
      this.drawMarks();
    }
    this.icon.setAttribute("d", player.playing ? PAUSE : PLAY);
    this.playButton.setAttribute("aria-label", player.playing ? "Pause" : player.atEnd ? "Play again from the start" : "Play");
    this.playButton.title = this.playButton.getAttribute("aria-label");
    const words = speedWords(player.speed);
    this.speedButton.textContent = words.short;
    this.speedButton.setAttribute("aria-label", `Speed: ${words.says}. Press to choose another.`);
    this.speedButton.title = words.says;
    this.fillSpeeds();
    this.place();
  }

  /** The steps the run is offered, slowest first, each with its words; the one in use is pressed. */
  fillSpeeds() {
    const player = this.player;
    this.speedList.replaceChildren(
      ...SPEEDS.map((speed) => {
        const words = speedWords(speed);
        return h(
          "button",
          { class: "tl-speed-step", type: "button", "aria-pressed": String(speed === player.speed), dataset: { speed: String(speed) }, onclick: () => (player.setSpeed(speed), this.showSpeeds(false), this.speedButton.focus()) },
          h("b", {}, words.short),
          h("span", {}, words.says.charAt(0).toLowerCase() + words.says.slice(1))
        );
      })
    );
  }

  /** Open or close the list of speeds. */
  showSpeeds(open) {
    if (!this.built) return;
    this.speedList.hidden = !open;
    this.classList.toggle("is-choosing", Boolean(open)); // the list stands over the cards beside the timeline while it is open
    this.speedButton.setAttribute("aria-expanded", String(Boolean(open)));
    if (open) {
      this.fillSpeeds();
      document.addEventListener("pointerdown", this.closeSpeeds, true);
      this.speedList.querySelector('[aria-pressed="true"]')?.focus();
    } else document.removeEventListener("pointerdown", this.closeSpeeds, true);
  }

  fraction(seconds) {
    const { start, end } = this.player;
    return end > start ? (seconds - start) / (end - start) : 0;
  }

  /** A tick per event, a taller line at the judged record, and a hatch where records are not valid. */
  drawMarks() {
    const run = this.run;
    this.marks.replaceChildren();
    this.flag.hidden = true;
    if (!run) return;
    const x = (seconds) => (this.fraction(seconds) * 1000).toFixed(1);
    if (run.validity) {
      // Stretches of the run whose records are not valid are greyed: nothing there is shown as data.
      let from = null;
      for (let k = 0; k <= run.count; k++) {
        const bad = k < run.count && !run.isValid(k);
        if (bad && from === null) from = k;
        if (!bad && from !== null) {
          const left = Number(x(run.t[from])), right = Number(x(run.t[Math.min(run.count - 1, k)]));
          this.marks.append(svg("rect", { class: "tl-invalid", x: left, y: 7, width: Math.max(3, right - left), height: 10 }));
          from = null;
        }
      }
    }
    for (const event of run.events) this.marks.append(svg("line", { class: "tl-tick", x1: x(event.time), x2: x(event.time), y1: 15, y2: 22 }));
    const judged = run.info.judged_s;
    if (Number.isFinite(judged)) {
      this.marks.append(svg("line", { class: "tl-judged", x1: x(judged), x2: x(judged), y1: 1, y2: 23 }));
      this.flag.hidden = false;
      this.flag.style.left = `${(this.fraction(judged) * 100).toFixed(2)}%`;
      this.flag.title = `The run was judged at ${clock(judged)}.`;
    }
  }

  /** Everything that follows the playhead. */
  place() {
    const player = this.player;
    if (!player || !this.built) return;
    const run = player.run;
    this.range.value = String(player.time);
    this.fill.style.width = `${(this.fraction(player.time) * 100).toFixed(2)}%`;
    if (!run) {
      this.now.textContent = "";
      this.rest.textContent = "";
      return;
    }
    const total = duration(player.end - player.start);
    this.now.textContent = clock(player.time);
    const parts = [` of ${total}`];
    if (run.events.length) parts.push(`${this.eventWord} ${run.eventsBy(player.time)} of ${run.events.length}`);
    if (!run.isValid(player.index)) parts.push("this record is not valid in the run");
    this.rest.textContent = parts.join(" · ");
    this.range.setAttribute("aria-valuetext", `${clock(player.time)} of ${total}`);
  }

  /** One step faster (1) or slower (-1) along the speeds the run is offered. */
  stepSpeed(direction) {
    const player = this.player;
    if (!player) return;
    const at = SPEEDS.indexOf(player.speed);
    const next = SPEEDS[Math.min(SPEEDS.length - 1, Math.max(0, (at < 0 ? SPEEDS.findIndex((speed) => speed >= player.speed) : at) + direction))];
    if (next !== undefined) player.setSpeed(next);
  }

  /** Jump to the next or the previous event of the run. */
  toEvent(direction) {
    const { player } = this;
    const times = player.run.events.map((event) => event.time);
    const target = direction > 0 ? times.find((time) => time > player.time + 1e-3) : [...times].reverse().find((time) => time < player.time - 1e-3);
    if (target !== undefined) player.seek(target);
  }
}

customElements.define("cells-timeline", CellsTimeline);
