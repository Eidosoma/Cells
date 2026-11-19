// The landing of the Experiments tab: a page of cards in bands (src/replay/landing.js reads them from cards.json), over
// the 3D stage, which draws nothing while it shows. It is shaped as a view (src/ui/viewer.js gives it the calls every
// view gets), so that a card's detail is the page's own panel (`select=card:<id>`), the List lists its cards and Escape
// closes what is open; it needs no 3D stage, and works where none can be drawn.
//
// What it fetches, and when: cards.json (beside the page) the first time the landing shows, never at the page's first
// entry; and each card's still (stills/…, beside the page) once it comes near the screen, with its size stated so that
// nothing moves when it arrives. It fetches no run and no model: a replay's card opens the view that exists for it, and
// that view fetches what it draws.
//
// Its first band stands open; every later band stands folded behind one control, a button in the file's words with the
// band's count of cards beside them (19 November 2026). A folded band's cards are made the first time it is shown, and
// folded again they are out of sight, out of the tab order and hidden from assistive technology; their stills are asked
// for only once the band is shown and they come near the screen. A card asked for (its detail's address, the List, the
// way back from its view) opens its band first. Which bands a visitor opened is kept in the browser's own storage.

import { h, svg, statusSwatch, formatDate } from "./dom.js";
import { loadBeside } from "../lenses/protein_shelves.js";
import { CARDS_FILE, CARD, cardsProblems, landingOf, faceOf, detailOf, opensOf, partNameOf, stillOf, openFirst, bandHolding, controlOf, readKept, writeKept } from "../replay/landing.js";

// How near the screen a still must come before it is fetched, in pixels above and below what is in sight.
export const STILL_MARGIN = 120;
// From how wide a window the cards leave the List room beside them, as they leave the panel room (narrower, the List lies
// over them as it does over every view: with both open there, the cards would keep too little room for a column).
export const LIST_ROOM = 1100;
const SIGNS = { yes: "M4 7.8l2.4 2.4L11 5.2", no: "M4.6 4.6l5.8 5.8M10.4 4.6l-5.8 5.8", mixed: "M7.5 3.4v5M5 5.9h5M5 11.2h5", none: "M4.6 7.5h5.8" };
const mark = (kind) => h("span", { class: `mark mark-${kind}`, "aria-hidden": "true" }, svg("svg", { viewBox: "0 0 15 15" }, svg("path", { d: SIGNS[kind] || SIGNS.none })));

export class LandingLens {
  /**
   * `replays` is the page's catalogue (scene.replays), for what a replay's card opens; `open(opened, card)` opens it (the
   * viewer's); `choose(id)` opens a card's detail in the panel; `openLens(id)` opens another view (the not-run line's);
   * `sourceUrl(source)` and `door(part)` are the scene's, for the detail; `statuses` the map's status ids.
   */
  constructor({ replays = null, open = () => {}, choose = () => {}, openLens = () => {}, sourceUrl = () => null, door = () => null, statuses = null, lensLabel = () => null, loader = loadBeside, document = globalThis.document } = {}) {
    this.id = "landing";
    this.replays = replays;
    this.open = open;
    this.choose = choose;
    this.openLens = openLens;
    this.sourceUrl = sourceUrl;
    this.door = door;
    this.statuses = statuses;
    this.lensLabel = lensLabel;
    this.loader = loader;
    this.document = document;
    this.data = null;
    this.landing = null;
    this.error = null;
    this.fetching = null;
    this.active = false;
    this.scrolled = 0;
    this.selected = null;
    this.dark = false;
    this.box = h("section", { class: "landing", "aria-label": "All experiments", hidden: true });
    this.status = h("div", { class: "landing-status" });
    this.inner = h("div", { class: "landing-inner" }, this.status);
    this.box.append(this.inner);
    this.box.addEventListener("scroll", () => this.active && (this.scrolled = this.box.scrollTop), { passive: true });
    this.stills = new Map(); // a still's image -> its card
    this.parts = new Map(); // a band's id -> its section, its control, its grid of cards, and whether it is open and made
    this.kept = new Set(); // the later bands a visitor opened with their controls (kept for the next visit)
    this.observer = typeof IntersectionObserver === "function" ? new IntersectionObserver((entries) => this.near(entries), { root: this.box, rootMargin: `${STILL_MARGIN}px 0px` }) : null;
    this.pickRoots = [];
    this.ready = Promise.resolve();
  }

  // ------------------------------------------------------------ the cards, fetched once

  /** Fetch the cards (once; again after a failure, when asked). Resolves when they are drawn or have failed. */
  load() {
    if (this.data) return Promise.resolve();
    if (this.fetching) return this.fetching;
    this.error = null;
    this.drawStatus();
    this.fetching = Promise.resolve()
      .then(() => this.loader(CARDS_FILE))
      .then((data) => {
        const problems = cardsProblems(data);
        if (problems.length) throw new Error(`${CARDS_FILE}: ${problems[0]}`);
        this.data = data;
        this.landing = landingOf(data);
        this.byId = new Map(data.cards.filter((card) => card?.id).map((card) => [card.id, card]));
        this.bandOf = new Map(this.landing.bands.flatMap((band) => band.cards.map((card) => [card.id, band])));
        this.build();
        this.onChrome?.();
        this.onPanel?.();
      })
      .catch((error) => {
        this.error = String(error?.message || error);
        this.drawStatus();
      })
      .finally(() => {
        this.fetching = null;
      });
    this.ready = this.fetching;
    return this.fetching;
  }

  drawStatus() {
    if (this.data) {
      this.status.replaceChildren();
      this.status.hidden = true;
      return;
    }
    this.status.hidden = false;
    this.status.replaceChildren(
      ...(this.error
        ? [h("p", { class: "landing-note", role: "alert" }, `The experiments' cards could not be fetched (${this.error}). The rest of the page works without them.`), h("button", { class: "pill-button landing-again", type: "button", onclick: () => this.load() }, "Try again")]
        : [h("p", { class: "landing-note", role: "status" }, "Fetching the experiments' cards…")])
    );
  }

  /** The page of cards, made once from the file (not on every redraw of the page's chrome, and not on a band's press). */
  build() {
    this.observer?.disconnect();
    this.stills.clear();
    this.parts.clear();
    // Open as the landing first opens: the first band, and the later bands this visitor opened before, where the browser kept them.
    const opened = openFirst(this.landing, readKept());
    this.kept = new Set([...opened].filter((id) => id !== this.landing.bands[0]?.id));
    const bands = this.landing.bands.map((band, order) => this.bandBox(band, order, opened.has(band.id)));
    const notRun = this.landing.notRun;
    const label = notRun?.lens ? this.lensLabel(notRun.lens) : null;
    const built = this.data.built_from;
    const foot = [
      notRun ? h("p", { class: "landing-not-run" }, label ? h("button", { class: "link-button", type: "button", dataset: { lens: notRun.lens }, onclick: () => this.openLens(notRun.lens) }, notRun.says) : notRun.says) : null,
      built?.map?.revision || built?.record?.revision ? h("p", { class: "landing-built" }, ["The cards read", built.map?.revision ? ` the Engine map at ${built.map.revision.slice(0, 8)}${built.map.as_of ? ` (${formatDate(built.map.as_of)})` : ""}` : "", built.map?.revision && built.record?.revision ? " and" : "", built.record?.revision ? ` the record at ${built.record.revision.slice(0, 8)}` : "", "."].join("")) : null,
    ].filter(Boolean);
    this.drawStatus();
    this.inner.replaceChildren(this.status, ...bands, ...foot);
    for (const [image, card] of this.stills) this.watch(image, card);
    this.setSelection(this.selected);
  }

  /** A band: its head (its label, its words and, where it folds, its control with its count), and its grid of cards. */
  bandBox(band, order, open) {
    const first = order === 0;
    const grid = h("div", { class: "landing-grid", id: `landing-band-${order}-cards` });
    const part = { band, first, open: first || open, made: false, grid, button: null, section: null };
    if (!first) {
      part.label = h("span", { class: "landing-fold-words" });
      part.count = h("span", { class: "landing-fold-count" });
      part.button = h("button", { class: "landing-fold", type: "button", "aria-controls": grid.id, onclick: () => this.setOpen(band.id, !part.open, { visitor: true }) }, h("span", { class: "landing-fold-chevron", "aria-hidden": "true" }), part.label, part.count);
    }
    part.section = h(
      "section",
      { class: `landing-band${first ? " is-first" : ""}`, dataset: { band: band.id }, "aria-label": band.label },
      h("div", { class: "landing-band-head" }, h("h2", { class: "landing-band-title" }, band.status && this.known(band.status) ? statusSwatch(band.status) : null, band.label), band.says ? h("p", { class: "landing-band-says" }, band.says) : null, part.button),
      grid
    );
    this.parts.set(band.id, part);
    this.draw(part);
    return part.section;
  }

  /** A band as it stands: open, its cards made (the first time it is shown) and shown; or folded, its cards out of sight. */
  draw(part) {
    if (part.open && !part.made) {
      part.grid.append(...part.band.cards.map((card) => this.cardOf(card)));
      part.made = true;
    }
    part.grid.hidden = !part.open;
    part.section.classList.toggle("is-folded", !part.open);
    if (part.button) {
      const control = controlOf(part.band, part.open);
      part.button.setAttribute("aria-expanded", String(part.open));
      part.label.textContent = control.says;
      part.count.textContent = String(control.count);
    }
  }

  /**
   * Opens or folds a later band. Shown, its stills are watched for, and fetched as they come near the screen; folded again,
   * those not yet fetched wait. A visitor's own press is kept for their next visit; a band opened for a card asked for is not.
   */
  setOpen(id, open, { visitor = false } = {}) {
    const part = this.parts.get(id);
    if (!part || part.first || part.open === Boolean(open)) return false;
    part.open = Boolean(open);
    this.draw(part);
    for (const [image, card] of this.stills) if (part.grid.contains(image) && !image.dataset.shown) (part.open ? this.watch(image, card) : this.observer?.unobserve(image));
    if (part.open) this.markChosen();
    if (visitor) {
      if (part.open) this.kept.add(id);
      else this.kept.delete(id);
      writeKept(this.kept);
    }
    return true;
  }

  /** Whether a band stands open (the first always does). */
  isOpen(id) {
    return Boolean(this.parts.get(id)?.open);
  }

  /** A card asked for: its band opens first. Its card's element, or null where the landing holds no such card. */
  reveal(id) {
    const band = bandHolding(this.landing, id);
    if (!band) return null;
    const opened = this.setOpen(band.id, true);
    const element = this.inner.querySelector(`[data-card="${CSS.escape(id)}"]`);
    return element ? { element, opened } : null;
  }

  /** The way back from a view to the card it was opened from: its band open, the keyboard on the card (where it was scrolled). */
  returnTo(id) {
    const found = id ? this.reveal(id) : null;
    if (!found) return;
    // A band opened only now moves the page under it: the card, its still above its title, is brought into sight.
    if (found.opened) found.element.scrollIntoView({ block: "nearest", inline: "nearest" });
    found.element.querySelector(".landing-open")?.focus({ preventScroll: true });
  }

  /** A still made: fetched now where nothing watches for the screen, else once it comes near it; a folded band's waits. */
  watch(image, card) {
    if (image.dataset.shown || image.closest(".landing-grid")?.hidden) return;
    if (this.observer) this.observer.observe(image);
    else this.show(image, card);
  }

  /** What a replay's card opens on this page (src/replay/landing.js, opensOf), or null. */
  opened(id) {
    const card = this.byId?.get(id);
    return card ? opensOf(card, this.replays) : null;
  }

  known(status) {
    return !this.statuses || this.statuses.has(status);
  }

  /** One card: in the order schema/EXPERIMENT_CARDS.md gives, each word the file's. */
  cardOf(card) {
    const opened = card.kind === "replay" || card.replay ? opensOf(card, this.replays) : null;
    const face = faceOf(card, { plays: opened });
    const replay = Boolean(opened);
    const still = stillOf(card, this.dark);
    // Where the card opens a part of its experiment, it says which, in the part's own name: its still pictures that part.
    const part = partNameOf(opened, this.replays);
    let image = null;
    if (still) {
      image = h("img", { class: "landing-still", width: still.width, height: still.height, alt: [face.first, `A still of ${face.title}${part ? `: ${part}` : ""}`].filter(Boolean).join(" "), decoding: "async", draggable: false });
      this.stills.set(image, card);
    }
    const level = face.level;
    const verdicts = face.verdicts.map((verdict) =>
      h(
        "li",
        { class: "landing-verdict" },
        h("span", { class: "landing-verdict-line" }, verdict.passed === null ? null : mark(verdict.passed ? "yes" : "no"), verdict.passed === null ? null : h("b", {}, verdict.passed ? "Passed" : "Failed"), verdict.count || verdict.day ? h("span", {}, [verdict.count, verdict.day ? formatDate(verdict.day) : null].filter(Boolean).join(" · ")) : null),
        verdict.scope ? h("span", { class: "landing-scope" }, verdict.scope.text) : null
      )
    );
    const runs = face.runs === null ? null : `${face.runs} ${face.runs === 1 ? "run" : "runs"}`;
    const foot = replay ? `Plays · ${runs}` : face.replay ? `Not played here${runs ? ` · ${runs}` : ""}` : face.rows !== null ? `${face.rows} ${face.rows === 1 ? "row" : "rows"} · no replay` : "The record · no replay";
    const pressed = () => (replay ? this.open(opened, card) : this.choose(CARD + card.id));
    return h(
      "article",
      { class: `landing-card is-${replay ? "replay" : "record"}`, dataset: { card: card.id, kind: String(card.kind || "") } },
      image ? h("div", { class: "landing-still-box", style: `aspect-ratio: ${still.width} / ${still.height}` }, image) : null,
      part ? h("p", { class: "landing-part" }, h("span", { class: "landing-part-label" }, "Opens on"), " ", part) : null,
      h(
        "h3",
        { class: "landing-title" },
        h("button", { class: "landing-open", type: "button", "aria-label": `${face.title}. ${replay ? "Open its replay" : "Open its record"}.`, onclick: pressed }, face.title)
      ),
      face.asks ? h("p", { class: "landing-asks" }, face.asks.text) : face.shows ? h("p", { class: "landing-asks" }, face.shows.text) : null,
      h(
        "div",
        { class: "landing-standing" },
        face.first ? h("p", { class: "landing-first" }, face.first) : null,
        level ? h("p", { class: "landing-level", title: level.says || "" }, level.status && this.known(level.status) ? statusSwatch(level.status) : null, level.label) : null,
        face.standing.text ? h("p", { class: "landing-says" }, face.standing.text) : null
      ),
      face.answer ? h("p", { class: "landing-answer" }, mark(face.answer.mark), face.answer.label) : null,
      verdicts.length ? h("ul", { class: "landing-verdicts" }, verdicts) : null,
      h("p", { class: "landing-foot" }, h("span", { class: "landing-runs" }, foot), h("button", { class: "landing-more", type: "button", "aria-label": `${face.title}: the record in full`, onclick: () => this.choose(CARD + card.id) }, "more"))
    );
  }

  /** Stills that came near the screen are fetched; one fetched once is never asked for again. */
  near(entries) {
    for (const entry of entries) {
      if (!entry.isIntersecting || entry.target.closest(".landing-grid")?.hidden) continue;
      const card = this.stills.get(entry.target);
      this.observer.unobserve(entry.target);
      if (card) this.show(entry.target, card);
    }
  }

  show(image, card) {
    const still = stillOf(card, this.dark);
    if (!still) return;
    image.dataset.shown = "1";
    // A page opened from disk carries its stills inside it, each as a data address (tools/export_page.mjs --standalone).
    const inline = this.document?.querySelector?.(`script[type="application/json"][data-file="${still.file}"]`);
    let source = still.file;
    try {
      if (inline) source = JSON.parse(inline.textContent);
    } catch {}
    if (image.getAttribute("src") !== source) image.src = source;
    image.addEventListener("error", () => image.closest(".landing-still-box")?.classList.add("is-missing"), { once: true });
  }

  // ------------------------------------------------------------ the calls every view gets

  activate() {
    this.active = true;
    this.box.hidden = false;
    if (!this.data) this.load();
    // Back from a view, at the place it was left.
    this.box.scrollTop = this.scrolled;
  }

  deactivate() {
    this.scrolled = this.box.scrollTop;
    this.active = false;
    this.box.hidden = true;
  }

  update() {
    return false; // nothing moves on the stage behind the cards: no frame is asked for
  }

  has(id) {
    return typeof id === "string" && id.startsWith(CARD) && Boolean(this.byId?.has(id.slice(CARD.length)));
  }

  /** A card's detail named before the cards are in (the address's select=card:…): the choice waits for them. */
  waitsFor(id) {
    return typeof id === "string" && id.startsWith(CARD) && !this.data && !this.error ? this.load() : null;
  }

  describe(id) {
    if (!this.has(id)) return null;
    const card = this.byId.get(id.slice(CARD.length));
    return detailOf(card, { band: this.bandOf.get(card.id), sourceUrl: this.sourceUrl, door: this.door, plays: card.replay ? opensOf(card, this.replays) : null, statuses: this.statuses, titleOf: (other) => this.byId.get(other)?.title || null });
  }

  sections() {
    return (this.landing?.bands || []).map((band) => ({ label: band.label, entities: band.cards.map((card) => ({ id: CARD + card.id, label: card.title || card.id, keywords: [card.id, card.standing?.part].filter(Boolean).join(" ") })) }));
  }

  entities() {
    return this.sections().flatMap((section) => section.entities);
  }

  chrome() {
    // No card, legend or timeline over the page of cards; the bar's stamp is the map's.
    return { quiet: true, legend: false };
  }

  setSelection(id) {
    this.selected = id || null;
    // A card asked for (its detail, from the address or the List) stands in an open band.
    if (this.selected?.startsWith(CARD) && this.landing) this.reveal(this.selected.slice(CARD.length));
    this.markChosen();
  }

  markChosen() {
    for (const element of this.inner.querySelectorAll(".landing-card")) element.classList.toggle("is-chosen", CARD + element.dataset.card === this.selected);
  }

  /** The page's theme: each still shown is the one for it. */
  applyPalette(palette) {
    const dark = Boolean(palette?.dark);
    if (dark === this.dark) return;
    this.dark = dark;
    for (const [image, card] of this.stills) if (image.dataset.shown) this.show(image, card);
  }

  setTheme(dark) {
    this.applyPalette({ dark });
  }

  setHover() {}
  setIsolate() {}
  /** A card chosen from the List or named by the address: its band open, the card brought into sight once the panel stands. */
  focus(id) {
    if (typeof id !== "string" || !id.startsWith(CARD)) return;
    const found = this.reveal(id.slice(CARD.length));
    if (!found) return;
    const bring = () => this.active && found.element.isConnected && found.element.scrollIntoView({ block: "nearest", inline: "nearest" });
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(bring);
    else bring();
  }
  dispose() {
    this.observer?.disconnect();
    this.box.remove();
  }
}

/** The landing's look, in the page's own tokens (src/page.css): its cards are the page's cards, its levels the map's swatches. */
export const LANDING_CSS = /* css */ `
/* Under the bar, never over it: the bar's tabs and the List stay in reach, and the keyboard reaches them before the cards. */
.landing { position: absolute; left: 0; right: 0; bottom: 0; top: var(--bar-height, 60px); padding-top: 4px; overflow-y: auto; overflow-x: hidden; background: var(--bg); overscroll-behavior: contain; }
.landing-inner { max-width: 1180px; margin: 0 auto; padding: 8px max(16px, env(safe-area-inset-right, 0px)) calc(32px + var(--sheet, 0px)) max(16px, env(safe-area-inset-left, 0px)); display: grid; gap: 26px; }
.landing-band { display: grid; gap: 12px; min-width: 0; }
.landing-band-head { display: grid; gap: 3px; }
.landing-band-title { display: flex; align-items: center; gap: 8px; font-family: var(--font-display); font-size: 12px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }
.landing-band-says { font-size: 12.5px; line-height: 1.45; color: var(--muted); max-width: 76ch; }
.landing-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(min(100%, 264px), 1fr)); align-items: start; }
/* A folded band: its head and its control stand; its cards are not drawn, not reached and not read out. */
.landing-grid[hidden] { display: none; }
.landing-fold { display: inline-flex; align-items: center; gap: 9px; width: fit-content; max-width: 100%; min-height: 36px; margin-top: 6px; padding: 6px 8px 6px 13px; border-radius: 999px; font-size: 13px; font-weight: 500; line-height: 1.3; color: var(--fg); background: var(--bg-raised); box-shadow: inset 0 0 0 1px var(--line); text-align: left; }
.landing-fold:hover { background: color-mix(in srgb, var(--fg) 7%, var(--bg-raised)); }
.landing-fold-chevron { flex: none; width: 7px; height: 7px; margin-right: 1px; border-right: 2px solid currentColor; border-bottom: 2px solid currentColor; transform: translateX(-1px) rotate(-45deg); }
.landing-fold[aria-expanded="true"] .landing-fold-chevron { transform: translateY(-2px) rotate(45deg); }
.landing-fold-words { min-width: 0; overflow-wrap: anywhere; }
.landing-fold-count { flex: none; min-width: 24px; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-variant-numeric: tabular-nums; text-align: center; color: var(--fg); background: color-mix(in srgb, var(--fg) 9%, transparent); }
@media (prefers-reduced-motion: no-preference) { .landing-fold-chevron { transition: transform .16s ease; } }
.landing-band.is-first .landing-grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); }
.landing-card { position: relative; display: grid; gap: 7px; align-content: start; min-width: 0; padding: 12px 14px 10px; border-radius: 12px; background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line), 0 10px 30px -22px rgb(0 0 0 / .45); }
.landing-card:hover { box-shadow: 0 0 0 1px var(--edge), 0 10px 30px -22px rgb(0 0 0 / .45); }
.landing-card.is-chosen { box-shadow: 0 0 0 2px var(--fg); }
/* A card brought into sight stands clear of a phone's panel sheet (its height is the viewer's --sheet, there only). */
.landing-card { scroll-margin-bottom: var(--sheet, 0px); }
.landing-card:has(.landing-open:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }
.landing-open:focus-visible { outline: none; }
.landing-still-box { margin: -12px -14px 2px; border-radius: 12px 12px 0 0; overflow: hidden; background: var(--plate); }
.landing-still-box.is-missing { display: none; }
/* Which part of its experiment a card opens (and its still pictures), in the part's own name. */
.landing-part { font-size: 12px; line-height: 1.35; color: var(--muted); }
.landing-part-label { margin-right: 7px; font-family: var(--font-display); font-size: 10.5px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; }
.landing-still { display: block; width: 100%; height: 100%; object-fit: cover; }
.landing-title { font-family: var(--font-display); font-size: 16px; font-weight: 600; line-height: 1.25; text-wrap: balance; }
.landing-band.is-first .landing-title { font-size: 19px; }
.landing-open { text-align: left; }
/* A press anywhere on a card is a press on its title: the title's button covers the card, and "more" stands above it. */
.landing-open::after { content: ""; position: absolute; inset: 0; border-radius: 12px; }
.landing-asks { font-size: 13px; line-height: 1.45; color: var(--fg); overflow-wrap: anywhere; }
.landing-standing { display: grid; gap: 4px; }
.landing-first { font-size: 13px; font-weight: 600; line-height: 1.4; }
.landing-level { display: inline-flex; align-items: center; gap: 7px; width: fit-content; padding: 2px 9px 2px 7px; border-radius: 999px; font-size: 12px; font-weight: 500; box-shadow: inset 0 0 0 1px var(--line); }
.landing-says { font-size: 12.5px; line-height: 1.45; color: var(--muted); overflow-wrap: anywhere; }
.landing-answer { display: flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; }
.landing-verdicts { display: grid; gap: 6px; }
.landing-verdict { display: grid; gap: 2px; font-size: 12.5px; }
.landing-verdict-line { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 7px; font-variant-numeric: tabular-nums; }
.landing-scope { font-size: 12px; line-height: 1.4; color: var(--muted); overflow-wrap: anywhere; }
.landing-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 2px; padding-top: 7px; border-top: 1px solid var(--line); font-size: 12px; color: var(--muted); }
.landing-more { position: relative; z-index: 1; padding: 3px 11px; border-radius: 999px; font-size: 12.5px; font-weight: 500; color: var(--fg); box-shadow: inset 0 0 0 1px var(--line); }
.landing-more:hover { background: color-mix(in srgb, var(--fg) 7%, transparent); }
.landing-status { display: grid; justify-items: start; gap: 10px; }
.landing-status[hidden] { display: none; }
.landing-note { font-size: 13px; color: var(--muted); }
.landing-not-run, .landing-built { font-size: 12.5px; color: var(--muted); }
.landing-not-run .link-button { color: var(--fg); }
.landing-built { margin-top: -18px; }
@media (min-width: 761px) { .has-panel .landing { right: calc(360px + 2 * max(16px, env(safe-area-inset-right, 0px))); } }
/* The List open beside the cards, as the panel is, on a window wide enough for both: a card chosen in it stands in sight. */
@media (min-width: ${LIST_ROOM}px) { .has-index .landing { left: calc(300px + 2 * max(16px, env(safe-area-inset-left, 0px))); } }
/* Over the page of cards a panel and the List stand on words, not on a picture: their ground is whole there, so that no
   card's words show through them (a card's detail on a phone lies over the cards). */
.on-landing cells-panel, .on-landing cells-index { background: var(--bg-raised); }
/* The way back to all experiments (src/ui/viewer.js, backButton): one place in every view the landing opens, under the bar at
   the left; the view's card stands under it on a wide window, and on a phone its folded line stands beside it. */
.exp-back { position: absolute; left: max(16px, env(safe-area-inset-left, 0px)); top: 64px; display: inline-flex; align-items: center; gap: 8px; z-index: 2; }
.exp-back-chevron { width: 7px; height: 7px; margin-left: 2px; border-left: 2px solid currentColor; border-bottom: 2px solid currentColor; transform: rotate(45deg); }
.has-back .view { top: 106px; }
.has-back .view.card { max-height: calc(100% - 106px - 16px); }
@media (max-width: 760px) {
  .exp-back { top: max(68px, calc(var(--bar-height, 0px) + 8px)); }
  .has-back .view { top: max(120px, calc(var(--bar-height, 0px) + 60px)); max-height: calc(100% - 120px - 160px); }
  .has-back.has-panel .view-toggle, .has-back.card-folds .view-toggle { left: calc(max(16px, env(safe-area-inset-left, 0px)) + var(--back-width, 0px) + 8px); max-width: calc(100% - 40px - var(--back-width, 0px)); }
}

@media (max-width: 760px) {
  .landing-inner { gap: 22px; }
  .landing-band.is-first .landing-grid, .landing-grid { grid-template-columns: minmax(0, 1fr); }
  .landing-more, .landing-again, .landing-not-run .link-button, .landing-fold { min-height: 44px; }
  .landing-open { min-height: 44px; }
}
`;
