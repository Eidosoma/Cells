// The About panel and the first-visit line (asked for by the owner on 20 November 2026): what the page is, in words
// taken from the project's own places, its views each as a door, and its source code. The words are written once, in
// data/site/about.json (cells.visualizer.about@1), which the page carries in its scene as `about`
// (tools/lib/build_page.mjs) and the site's staging reads from the staged page (tools/stage_site.mjs).
//
// - **The panel** stands in the side panel's place (a sheet on a phone), over whatever part is chosen: closed, the view
//   is as it was, the chosen part's panel too. It opens from the bar's About button, from the name "Cells" in the bar's
//   corner, from the line's About, and from the address's `#about`, which passes the artifact's frame as every `#name`
//   does. `about` is read, never written: a tab press writes `#<view>`, and no view has the id `about`.
// - **The line** says in one sentence what the page is, with About, the source code (a new tab) and a close button.
//   Closed, it stays closed in this browser (its storage, read and written so that a refusal breaks nothing: where
//   nothing can be kept, it shows again on the next visit). Opening About closes it too. On a wide window it takes the
//   first band under the bar where it covers nothing the page has put over the picture and none of the names the view
//   shows (placeIntro): it yields to them, never they to it, so every view draws what it drew without it. It stands under
//   every card and every name, and waits out of sight where no band is free, on a window narrower than 760 px (a phone
//   has no such band under its bar), where no 3D is drawn, and while a panel or a sheet is open.
// - **The site's text without script** (tools/stage_site.mjs, the element `cells-text`) is put away once the page has drawn.
//
// What the page knows of itself it says: the map's date and the engine revision of its stamp, and on the site the
// release its host profile names (src/core/host.js). Nothing else.

import { h, svg, formatDate } from "./dom.js";

export const ABOUT_FORMAT = "cells.visualizer.about@1";
/** The address's name for the panel (`#about`): no view has this id (tests/stage_site.test.mjs holds it). */
export const ABOUT = "about";
/** Where the browser keeps that the line was closed. */
export const INTRO_KEY = "cells-visualizer.intro.closed";
/** The site's text without script (tools/stage_site.mjs writes it), put away once the page has drawn. */
export const TEXT_ELEMENT = "cells-text";
/** A link that opens a new tab, safely: the page it opens gets no hold on this one, and no address of it. */
export const NEW_TAB = Object.freeze({ target: "_blank", rel: "noopener noreferrer" });

const text = (value) => (typeof value === "string" && value.trim() ? value.trim() : null);
const outside = (url) => /^(https:\/\/|mailto:)/.test(String(url || ""));

/** The About words a scene carries (`about`), each piece checked; null where it carries none of this format. */
export function aboutOf(scene) {
  const about = scene?.about;
  if (!about || about.format !== ABOUT_FORMAT || !text(about.name) || !text(about.line?.text) || !/^https:\/\//.test(about.source?.url || "")) return null;
  const said = (items) => (Array.isArray(items) ? items.map((item) => text(item?.text)).filter(Boolean) : []);
  return {
    name: about.name.trim(),
    title: text(about.title?.text),
    description: text(about.description?.text),
    line: about.line.text.trim(),
    lead: said(about.lead),
    reading: said(about.reading),
    views: (Array.isArray(about.views) ? about.views : []).filter((view) => text(view?.id) && text(view?.text)).map((view) => ({ id: view.id, text: view.text.trim() })),
    source: { label: text(about.source.label) || "Source code", url: about.source.url, licence: text(about.source.licence?.name) ? { name: about.source.licence.name.trim(), path: text(about.source.licence.path) } : null },
    // What names anyone: the credit's words, and the organisation they name (the structured data's author and publisher).
    credit: text(about.credit?.text) ? { text: about.credit.text.trim(), organisation: text(about.credit.organisation) } : null,
    contact: about.contact && text(about.contact.label) && outside(about.contact.url) ? { label: about.contact.label.trim(), url: about.contact.url } : null,
    links: (Array.isArray(about.links) ? about.links : []).filter((link) => text(link?.label) && outside(link?.url)).map((link) => ({ label: link.label.trim(), url: link.url })),
  };
}

/** Whether an address's `#name` asks for the panel. */
export const aboutAsked = (hash) => String(hash ?? "").replace(/^#/, "") === ABOUT;

/** The licence's file at the revision the map was read at (the scene's source base), where that base is the source's own repository; else null. */
export function licenceUrl(about, meta) {
  const base = meta?.source_base_url, path = about?.source?.licence?.path;
  return base && path && String(base).startsWith(`${about.source.url}/blob/`) ? `${base}${path}` : null;
}

/** What the page knows of itself, as label and value: the map's stamp (its date and engine revision) and, on the site, its release. */
export function pageFacts(meta, host, formatDate = (date) => date) {
  const stamp = [meta?.as_of ? `As of ${formatDate(meta.as_of)}` : "", meta?.revision ? `main ${meta.revision}` : ""].filter(Boolean).join(" · ");
  return [stamp ? ["Map", stamp] : null, host?.release ? ["Release", host.release] : null].filter(Boolean);
}

/** Whether the line was closed in this browser; false where its storage is refused or keeps nothing. */
export function introClosed(store = () => globalThis.localStorage) {
  try {
    return store()?.getItem(INTRO_KEY) === "closed";
  } catch {
    return false;
  }
}

/** Keeps that the line was closed; false where the browser keeps nothing (the line then shows on the next visit). */
export function keepIntroClosed(store = () => globalThis.localStorage) {
  try {
    const storage = store();
    if (!storage) return false;
    storage.setItem(INTRO_KEY, "closed");
    return true;
  } catch {
    return false;
  }
}

/**
 * Where the first-visit line stands, in the frame's coordinates: in the first band from `top` (under the bar) down to
 * `depth` below it (and never past `reach` of the frame's height: it stays under the bar, never among a view's names further
 * down) where a box of `size` comes within `gap` of none of `taken` (the rectangles of what the
 * page has put over the picture; a rectangle may carry its own clearance, `gapX` across and `gapY` up and down), within
 * `side` of the frame's edges, as near the frame's middle as that band allows. Null where no band holds it: the line then
 * waits, out of sight.
 */
export function placeIntro({ width, height, top, taken = [], size, gap = 8, side = 16, step = 2, reach = 0.5, depth = Infinity }) {
  if (!(size?.width > 0 && size?.height > 0) || size.width > width - 2 * side) return null;
  for (let y = Math.ceil(top); y + size.height <= height * reach && y <= top + depth; y += step) {
    const blocks = taken
      .filter((rect) => rect.top < y + size.height + (rect.gapY ?? gap) && rect.bottom > y - (rect.gapY ?? gap))
      .map((rect) => [rect.left - (rect.gapX ?? gap), rect.right + (rect.gapX ?? gap)])
      .sort((a, b) => a[0] - b[0]);
    const free = [];
    let x = side;
    for (const [from, to] of blocks) {
      if (from > x) free.push([x, Math.min(from, width - side)]);
      x = Math.max(x, to);
    }
    if (x < width - side) free.push([x, width - side]);
    const middle = width / 2;
    const fits = free
      .filter(([from, to]) => to - from >= size.width)
      .map(([from, to]) => Math.min(Math.max(middle - size.width / 2, from), to - size.width))
      .sort((a, b) => Math.abs(a + size.width / 2 - middle) - Math.abs(b + size.width / 2 - middle));
    if (fits.length) return { left: Math.round(fits[0]), top: y };
  }
  return null;
}

/** A link to another site, opened in a new tab, with words for a screen reader that say so. */
function newTab(url, words, extra = {}) {
  // The arrow is drawn, not typed, so it does not depend on a font having it.
  const away = svg("svg", { class: "about-away", viewBox: "0 0 12 12", "aria-hidden": "true" }, svg("path", { d: "M3.5 8.5L8.5 3.5M4.5 3.5H8.5V7.5" }));
  return h("a", { href: url, ...NEW_TAB, ...extra }, words, away, h("span", { class: "about-quiet" }, " (opens in a new tab)"));
}

/**
 * The page's part of About: the bar's button and the name in its corner, the line under the bar, and the panel's words.
 * `viewer` is the <cells-viewer>; it calls `start()` once its scene is drawn, `toggle()`, `place()` and `panel()`.
 */
export class AboutPart {
  constructor(viewer) {
    this.viewer = viewer;
    this.about = null;
    this.button = h("button", { class: "pill-button about-button", type: "button", "aria-pressed": "false", hidden: true, onclick: () => this.toggle(undefined, { from: this.button }) }, "About");
    // The name in the bar's corner is a second way to the panel, for the pointer; the About button beside List is the keyboard's.
    this.brand = h("button", { class: "brand-button", type: "button", tabIndex: -1, "aria-label": "About Cells", onclick: () => this.about && this.toggle(undefined, { from: this.button }) }, h("b", {}, "Cells"));
    this.line = h("div", { class: "intro", hidden: true });
    this.placed = null;
  }

  /** Once the scene is in: the words, the line on a first visit, `#about` in the address, and the site's text put away. */
  start() {
    const viewer = this.viewer;
    this.about = aboutOf(viewer.model?.raw);
    const document_ = viewer.ownerDocument;
    const putAway = () => document_?.getElementById?.(TEXT_ELEMENT)?.setAttribute("hidden", "");
    // The site's text stands until the page has drawn: its first frame, or at once where no 3D can be drawn.
    if (viewer.stage) {
      const once = () => {
        putAway();
        viewer.stage.afterRender.delete?.(once);
      };
      viewer.stage.afterRender.add(once);
    } else putAway();
    if (!this.about) return;
    this.button.hidden = false;
    // The bar was fitted without the button: fitted again with it (the tabs' row, the species switch's place, the squeeze),
    // and the tab of the view shown brought into sight in the row, now narrower.
    viewer.renderChrome();
    viewer.showPressedTab?.();
    if (!introClosed()) this.showLine();
    // The address names the panel: as the page opens, and when only its #name changes.
    if (aboutAsked(location.hash)) this.toggle(true);
    globalThis.addEventListener?.("hashchange", () => aboutAsked(location.hash) && !viewer.state.about && this.toggle(true));
  }

  showLine() {
    const about = this.about;
    const close = h("button", { class: "icon-button intro-close", type: "button", "aria-label": "Close this line", onclick: () => this.closeLine({ keep: true, focus: true }) }, "×");
    this.line.replaceChildren(
      h("p", { class: "intro-text" }, about.line),
      h(
        "p",
        { class: "intro-actions" },
        h("button", { class: "link-button intro-about", type: "button", onclick: (event) => this.toggle(true, { from: this.button, event }) }, "About"),
        newTab(about.source.url, about.source.label, { class: "intro-source" }),
        close
      )
    );
    this.line.setAttribute("role", "region");
    this.line.setAttribute("aria-label", `${about.name}: a first look`);
    this.lineOpen = true;
    this.line.hidden = false;
    this.line.classList.add("is-waiting");
    this.place();
    // Its place follows what the page puts over the picture and the names the view shows: a frame drawn, the window's size,
    // a card or panel shown or put away (a change of `hidden` in the frame, or of the frame's own classes), looked at no
    // more than four times a second, so that a moving picture costs its frames nothing more.
    const frame = this.viewer.frame;
    this.follow = () => {
      if (this.pending) return;
      this.pending = setTimeout(() => {
        this.pending = 0;
        this.place();
      }, 250);
    };
    this.viewer.stage?.afterRender.add(this.follow);
    globalThis.addEventListener?.("resize", this.follow);
    this.watching = [new MutationObserver(this.follow), new MutationObserver(this.follow)];
    this.watching[0].observe(frame, { subtree: true, attributes: true, attributeFilter: ["hidden"] });
    this.watching[1].observe(frame, { attributes: true, attributeFilter: ["class"] });
  }

  /** Closed by its button, or by opening About: kept closed where the browser keeps it. */
  closeLine({ keep = true, focus = false } = {}) {
    if (!this.lineOpen) return;
    if (keep) keepIntroClosed();
    this.lineOpen = false;
    this.line.hidden = true;
    this.line.replaceChildren();
    this.viewer.stage?.afterRender.delete?.(this.follow);
    globalThis.removeEventListener?.("resize", this.follow);
    for (const watch of this.watching || []) watch.disconnect();
    if (this.pending) clearTimeout(this.pending);
    this.pending = 0;
    if (focus) this.button.focus({ preventScroll: true });
  }

  /** What the page has put over the picture under the bar, in the frame's coordinates: every card, switch and note, and every name the view shows, that the line must keep clear of. */
  taken() {
    const viewer = this.viewer, frame = viewer.frame.getBoundingClientRect();
    const seen = (element) => element && !element.hidden && element.getClientRects().length > 0;
    // (Not the species' dropdown: it opens over everything for a moment, the line under it.)
    const elements = [viewer.legend, viewer.viewCard, viewer.viewToggle, viewer.backButton, viewer.rail, viewer.railToggle, viewer.panel, viewer.index, viewer.timeline, viewer.sweepCard, viewer.scaleBar, viewer.caveat, viewer.hint, viewer.atlasNav?.trail, viewer.atlasNav?.map, viewer.landingView?.box];
    const rects = elements.filter(seen).map((element) => element.getBoundingClientRect());
    // The names on the picture the view shows now: the line yields to them, so that none is hidden for it. It keeps from a
    // name the clearance a name keeps from a card (src/core/labels.js: 6 px across, 2 px up and down).
    const names = [...(viewer.labelBox?.querySelectorAll(".label:not(.is-off)") || [])].map((label) => label.getBoundingClientRect());
    // Where no 3D can be drawn, the page's note says so in a line of words at the head of its box, which reaches the foot.
    if (seen(viewer.fallback)) {
      const range = document.createRange();
      range.selectNodeContents(viewer.fallback);
      rects.push(range.getBoundingClientRect());
    }
    const inFrame = (rect, more = {}) => ({ left: rect.left - frame.left, top: rect.top - frame.top, right: rect.right - frame.left, bottom: rect.bottom - frame.top, ...more });
    const real = (rect) => rect.width > 0 && rect.height > 0;
    return [...rects.filter(real).map((rect) => inFrame(rect)), ...names.filter(real).map((rect) => inFrame(rect, { gapX: 6, gapY: 2 }))];
  }

  /** Put the line where it covers nothing, or out of sight while no band holds it and while a panel or a sheet is open. */
  place() {
    if (!this.lineOpen) return;
    const viewer = this.viewer, line = this.line;
    // A phone has no band under its bar that is not a card's or a view's own: there the line waits (the bar's About is the way
    // in). So it does where no 3D is drawn: the page's note on that lies over the whole picture and would take its presses.
    const open = Boolean(viewer.state.selected) || Boolean(viewer.state.about) || viewer.clientWidth < 760 || !viewer.stage;
    let spot = null;
    if (!open) {
      const frame = viewer.frame.getBoundingClientRect();
      const size = { width: Math.ceil(line.offsetWidth), height: Math.ceil(line.offsetHeight) };
      const bar = viewer.bar.getBoundingClientRect();
      // Close under the bar (2 px below its box, whose own padding keeps the bar's controls 12 px above), and no deeper than
      // about three rows of names under it: it keeps as little as it can of the picture's head, and never stands in the picture.
      spot = placeIntro({ width: frame.width, height: frame.height, top: bar.bottom - frame.top + 2, taken: this.taken(), size, depth: 96 });
    }
    const key = spot ? `${spot.left},${spot.top}` : "none";
    if (key === this.placed) return;
    this.placed = key;
    line.classList.toggle("is-waiting", !spot);
    line.toggleAttribute("inert", !spot);
    if (spot) line.style.transform = `translate(${spot.left}px, ${spot.top}px)`;
  }

  /** Open or close the panel. `from`: the control the focus goes back to when it closes. */
  toggle(force, { from = null } = {}) {
    const viewer = this.viewer;
    if (!this.about) return;
    const open = force ?? !viewer.state.about;
    if (open === Boolean(viewer.state.about)) {
      if (open) this.focusPanel();
      return;
    }
    viewer.state.about = open;
    this.button.setAttribute("aria-pressed", String(open));
    if (open) {
      this.returnTo = from || this.button;
      this.closeLine({ keep: true });
      this.made = null;
    }
    viewer.renderPanel();
    if (open) this.focusPanel();
    else if (this.returnTo?.isConnected && this.returnTo.getClientRects().length && from !== false) this.returnTo.focus({ preventScroll: true });
    this.place();
  }

  focusPanel() {
    queueMicrotask(() => this.viewer.panel.querySelector(".about-head h2")?.focus({ preventScroll: true }));
  }

  /** The panel's words, made once each time it opens: its head, the words, the views as doors, the source, what the page knows of itself. */
  panel() {
    if (this.made) return this.made;
    const viewer = this.viewer, about = this.about, meta = viewer.model?.meta || {};
    const facts = pageFacts(meta, viewer.host, formatDate);
    const views = viewer.views.map((view) => ({ id: view.id, label: view.label, text: about.views.find((item) => item.id === view.id)?.text || null }));
    // A door does what its tab does when pressed (the Experiments tab, pressed in a view of its own, goes back to its landing).
    const door = (id) => {
      this.toggle(false, { from: false });
      const tab = viewer.switchBox.querySelector(`[data-lens="${id}"]`);
      if (id !== viewer.state.lens || (id === "experiments" && !viewer.state.landing)) tab?.click();
      tab?.focus({ preventScroll: true });
    };
    const head = h(
      "header",
      { class: "panel-head about-head" },
      h("div", {}, h("p", { class: "eyebrow" }, "About"), h("h2", { tabIndex: -1 }, about.name)),
      h("button", { class: "icon-button", type: "button", "aria-label": "Close", onclick: () => this.toggle(false) }, "×")
    );
    const body = h(
      "div",
      { class: "panel-body about-body" },
      about.lead.map((words, k) => h("p", { class: k ? "about-text" : "panel-plain" }, words)),
      // The source code, in a new tab (its licence is not linked here: the owner, 20 November 2026).
      h("p", { class: "about-source" }, newTab(about.source.url, about.source.label, { class: "about-source-link" })),
      about.credit ? h("p", { class: "about-text about-credit" }, about.credit.text) : null,
      about.contact || about.links.length ? h("ul", { class: "about-links" }, [...about.links, ...(about.contact ? [about.contact] : [])].map((link) => h("li", {}, /^mailto:/.test(link.url) ? h("a", { href: link.url }, link.label) : newTab(link.url, link.label)))) : null,
      h("h3", {}, "Views"),
      h(
        "ul",
        { class: "about-views" },
        views.map((view) => h("li", {}, h("p", { class: "panel-door" }, h("button", { class: "link-button", type: "button", dataset: { door: view.id }, onclick: () => door(view.id) }, `${view.label} →`)), view.text ? h("p", { class: "about-text" }, view.text) : null))
      ),
      about.reading.length ? [h("h3", {}, "How to read it"), about.reading.map((words) => h("p", { class: "about-text" }, words))] : null,
      facts.length ? [h("h3", {}, "This page"), h("dl", { class: "facts" }, facts.map(([label, value]) => [h("dt", {}, label), h("dd", {}, value)]))] : null
    );
    this.made = [head, body];
    return this.made;
  }
}

/** The look of the line and the panel's own pieces, in the page's tokens (src/page.css). */
export const ABOUT_CSS = /* css */ `
.brand-button { display: inline-flex; align-items: baseline; border-radius: 6px; }
.brand-button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.intro { position: absolute; left: 0; top: 0; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 2px 14px; width: max-content; max-width: min(640px, calc(100% - 32px)); padding: 2px 4px 2px 14px; border-radius: 12px; background: color-mix(in srgb, var(--bg-raised) 96%, transparent); box-shadow: 0 0 0 1px var(--line), 0 10px 30px -18px rgb(0 0 0 / .45); font-size: 13px; line-height: 1.35; transition: opacity .25s ease; }
/* Its words let a press through to the picture under them, as the hint and the caveat do; only its three controls take one. */
.intro { pointer-events: none; }
.intro button, .intro a { pointer-events: auto; }
.intro.is-waiting { visibility: hidden; opacity: 0; transition: none; }
.intro-text { flex: 1 1 auto; color: var(--fg); }
.intro-actions { display: flex; align-items: center; gap: 2px 12px; flex: none; }
.intro-about { font-weight: 600; }
.intro a { color: var(--accent); text-underline-offset: 3px; }
.intro-close { width: 22px; height: 22px; font-size: 18px; }
.about-quiet { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.about-away { width: .78em; height: .78em; margin-left: 3px; vertical-align: -1px; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.about-text { font-size: 13px; line-height: 1.5; color: var(--muted); overflow-wrap: anywhere; }
.about-source { font-size: 14px; font-weight: 500; }
.about-source a, .about-links a { color: var(--accent); text-underline-offset: 3px; }
.about-source .about-source-link { font-weight: 600; }
.about-links { display: grid; gap: 4px; font-size: 13px; }
.about-views { display: grid; gap: 10px; }
.about-views .about-text { margin-top: 1px; }
.about-head h2:focus { outline: none; }
.about-head h2:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
@media (max-width: 759px) {
  /* Pressed with a thumb, as every button of the bar (44 px), also while the bar's squeeze keeps the name out of sight. */
  .brand-button { min-width: 44px; min-height: 44px; align-items: center; }
  /* With About in the bar the tabs' row is narrower and scrolls further; the browser scrolls it by whole pixels, so at the
     row's far end its last tab could stand a fraction of a pixel past the row's edge: the row ends with 2 px of room. */
  .bar[data-squeeze~="5"] .switch { padding-right: 2px; }
  .about-source a, .about-links a { display: inline-flex; align-items: center; min-height: 44px; }
}
@media (prefers-reduced-motion: reduce) { .intro { transition: none; } }
.is-still .intro { transition: none; }
`;
