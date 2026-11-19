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
//
// A run may count its time in steps of its own (its time base, src/replay/player.js): the speeds,
// their words and the read-out are then the base's, and a run that names none keeps seconds.
//
// A time base may also lay the track out itself (`place(time, speed)`, `timeAt(place, speed)`: the tissue's play,
// src/replay/tissue_play.js, whose track is the play and not the run's even time), and a binding may ask for its events
// as stops (`stops: true`): each event with a label becomes a mark that can be pressed to go there, with buttons
// for the previous and the next one beside play.
//
// A species' life stages (src/scene/life_stages.js, journeyOf) are bound the same way, with a few words more: `label`
// names the slider ("Life stage"), `read(time)` gives the read-out's words, `play: false` hides play where nothing
// plays, `named: true` writes each stop's short name under it, and `onStop(event)` is called when a stop is pressed
// (or Page Up and Page Down reach one) in place of moving there. A stop whose event says `enterable: false` (a stage
// named and not drawn) is hollow, says so, and Page Up and Page Down pass over it.

import { h, svg } from "./dom.js";
import { clock, duration } from "../replay/format.js";
import { SPEEDS, SECONDS, whereWords } from "../replay/player.js";

const RANGE_LABEL = "Time in the run";

const PLAY = "M7 4.5v15l12-7.5z", PAUSE = "M6.5 4.5h4v15h-4zM13.5 4.5h4v15h-4z";

class CellsTimeline extends HTMLElement {
  connectedCallback() {
    if (this.built) return;
    this.built = true;
    this.icon = svg("path", { d: PLAY });
    this.playButton = h("button", { class: "tl-play", type: "button", onclick: () => this.player?.toggle() }, svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" }, this.icon));
    // The previous and the next stop, where a binding asks for stops (drawn, not typed: no font is needed for them).
    const stepButton = (direction) => h("button", { class: "tl-step", type: "button", hidden: true, dataset: { step: direction > 0 ? "next" : "previous" }, onclick: () => this.toEvent(direction) }, svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" }, svg("path", { d: direction > 0 ? "M6 5v14l9-7zM16 5h3v14h-3z" : "M18 5v14l-9-7zM5 5h3v14H5z" })));
    this.previousButton = stepButton(-1);
    this.nextButton = stepButton(1);
    this.stops = h("div", { class: "tl-stops", hidden: true });
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
      this.previousButton,
      this.nextButton,
      h("div", { class: "tl-body" }, h("div", { class: "tl-track" }, h("div", { class: "tl-rail" }, this.fill), this.marks, this.flag, this.range, this.stops), h("p", { class: "tl-read" }, this.now, this.rest)),
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
    this.range.addEventListener("input", () => this.player?.seek(this.laid() ? this.player.base.timeAt(Number(this.range.value), this.player.speed) : Number(this.range.value)));
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
      else if ((event.key === " " || event.key === "Enter") && this.canPlay !== false) player.toggle();
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
  bind(player, { eventWord = "event", stops = false, play = true, label = RANGE_LABEL, read = null, onStop = null, named = false } = {}) {
    // What a binding may change while it follows the same player (a life stage's strip: whether play shows here).
    const same = this.player === player && this.eventWord === eventWord && this.run === player.run && this.withStops === stops;
    const looks = `${play}|${label}|${named}`;
    this.read = read;
    this.onStop = onStop;
    if (same && looks === this.looks) return;
    this.canPlay = play;
    this.label = label;
    this.named = named;
    this.looks = looks;
    if (same) {
      if (this.built) {
        this.laidOut = null; // the stops are drawn again with their names
        this.sync();
      }
      return;
    }
    this.unbind();
    this.player = player;
    this.eventWord = eventWord;
    this.withStops = stops;
    this.laidOut = null;
    this.onTime = () => this.place();
    this.onState = () => this.sync();
    player.addEventListener("time", this.onTime);
    player.addEventListener("state", this.onState);
    // The speeds offered are one list for every player (src/replay/player.js, refilled when a player loads a run): a player
    // bound again after another loaded its run gets its own back.
    if (player.run) SPEEDS.splice(0, SPEEDS.length, ...player.base.speedsFor(player.end - player.start));
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
    // The track is laid out again when the run changes, or the speed changes how a time base lays it out.
    const laid = `${this.laid() ? player.speed : "even"}|${this.withStops}`;
    if (run !== this.run || laid !== this.laidOut) {
      this.run = run;
      this.laidOut = laid;
      this.range.min = this.laid() ? "0" : String(player.start);
      this.range.max = this.laid() ? "1" : String(player.end);
      this.drawMarks();
    }
    this.classList.toggle("has-stops", Boolean(this.withStops && run?.events?.length));
    for (const button of [this.previousButton, this.nextButton]) {
      button.hidden = !(this.withStops && run?.events?.length);
      const word = this.eventWord, which = button.dataset.step === "next" ? "next" : "previous";
      button.setAttribute("aria-label", `Go to the ${which} ${word}`);
      button.title = `The ${which} ${word}`;
    }
    this.playButton.hidden = this.canPlay === false;
    this.classList.toggle("no-play", this.canPlay === false); // its column goes with it (styles.js)
    this.classList.toggle("is-stages", Boolean(this.onStop)); // a strip of stages: dots, not ticks (styles.js)
    this.classList.toggle("has-names", Boolean(this.named));
    this.range.setAttribute("aria-label", this.label || RANGE_LABEL);
    this.icon.setAttribute("d", player.playing ? PAUSE : PLAY);
    this.playButton.setAttribute("aria-label", player.playing ? "Pause" : player.atEnd ? "Play again from the start" : "Play");
    this.playButton.title = this.playButton.getAttribute("aria-label");
    const words = (player.base || SECONDS).words(player.speed);
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
        const words = (player.base || SECONDS).words(speed);
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
      // The list opens upward from the timeline and stays under the page's bar. On a phone with a panel open the
      // timeline stands high, on the panel's top edge: where there is more room below it, the list opens downward,
      // over the panel. Either way it scrolls within the room it has (styles.js shades its edge).
      const frame = this.offsetParent?.getBoundingClientRect() ?? { top: 0, bottom: window.innerHeight };
      const at = this.getBoundingClientRect();
      const above = at.top - frame.top - 6 - 68, below = frame.bottom - at.bottom - 6 - 8;
      const down = above < 220 && below > above;
      this.speedList.classList.toggle("opens-down", down);
      this.speedList.style.maxHeight = `${Math.round(Math.max(88, Math.min(420, window.innerHeight * 0.6, down ? below : above)))}px`;
      document.addEventListener("pointerdown", this.closeSpeeds, true);
      this.speedList.querySelector('[aria-pressed="true"]')?.focus();
    } else document.removeEventListener("pointerdown", this.closeSpeeds, true);
  }

  /** Whether the run's time base lays the track out itself (the tissue's play). */
  laid() {
    return typeof this.player?.base?.place === "function";
  }

  fraction(seconds) {
    const { start, end } = this.player;
    if (this.laid()) return this.player.base.place(seconds, this.player.speed);
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
    // Stops: each event that has words becomes a mark to press, named by its words.
    this.stops.hidden = !this.withStops;
    this.stops.replaceChildren(
      ...(this.withStops ? run.events.filter((event) => event.label) : []).map((event) => {
        const named = event.enterable === false;
        const said = String(event.says || event.label).replace(/\.+$/, "");
        return h(
          "button",
          { class: `tl-stop${named ? " is-named" : ""}`, type: "button", dataset: { time: String(event.time), ...(event.stage ? { stage: event.stage } : {}) }, style: `left:${(this.fraction(event.time) * 100).toFixed(2)}%`, "aria-label": named ? `${said}. Opens what is known of it` : `Go to ${event.label}`, title: said, onclick: () => (this.onStop ? this.onStop(event) : (this.player?.pause(), this.player?.seek(event.time))) },
          this.named ? h("span", { class: "tl-stop-name", "aria-hidden": "true" }, event.short || event.label) : null
        );
      })
    );
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
    this.range.value = String(this.laid() ? this.fraction(player.time) : player.time);
    for (const stop of this.stops.children) stop.toggleAttribute("aria-current", Math.abs(Number(stop.dataset.time) - player.time) < 1e-9);
    this.fill.style.width = `${(this.fraction(player.time) * 100).toFixed(2)}%`;
    if (!run) {
      this.now.textContent = "";
      this.rest.textContent = "";
      return;
    }
    // The run's own time, and what it lies in: its length, or, for a run whose records start later, its first and last record.
    // A binding that gives its own words (a life stage's strip) says where on the strip the playhead stands.
    const { now, of } = this.read ? this.read(player.time) : whereWords({ time: player.time, start: player.start, end: player.end, base: player.base || SECONDS });
    this.now.textContent = now;
    const parts = [of];
    if (run.events.length && !this.read) parts.push(`${this.eventWord} ${run.eventsBy(player.time)} of ${run.events.length}`);
    if (!run.isValid(player.index)) parts.push("this record is not valid in the run");
    this.rest.textContent = parts.join(" · ");
    this.range.setAttribute("aria-valuetext", `${now}${of}`);
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
    if (!player?.run) return;
    // A binding that takes its stops itself (a life stage's strip) is handed the next one that can be entered.
    if (this.onStop && this.withStops) {
      const open = player.run.events.filter((event) => event.label && event.enterable !== false);
      const next = direction > 0 ? open.find((event) => event.time > player.time + 1e-3) : [...open].reverse().find((event) => event.time < player.time - 1e-3);
      if (next) this.onStop(next);
      return;
    }
    const times = player.run.events.map((event) => event.time);
    const target = direction > 0 ? times.find((time) => time > player.time + 1e-3) : [...times].reverse().find((time) => time < player.time - 1e-3);
    if (target !== undefined) {
      if (this.withStops) player.pause();
      player.seek(target);
    }
  }
}

customElements.define("cells-timeline", CellsTimeline);
