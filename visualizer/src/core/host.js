// The host profile (docs/HOSTING_AND_API.md, section 3): what the page's host allows, as one small JSON block that the
// site's staging writes into each release's page (tools/stage_site.mjs):
//
//   <script type="application/json" id="cells-host">{"format": "cells.visualizer.host@1", "release": "v49", "links": "query", "api": null}</script>
//
// The page learns its host from it and never from its own address. A page with no block (the artifact, the local server,
// a file on disk) has the defaults, which are the artifact's: no release named, only the outer link's #name is a link,
// and no API. A block that cannot be read gives the defaults too, with what was wrong in `problem`; nothing is thrown or
// logged. For now the viewer only keeps the profile (`viewer.host`) and shows nothing new by it.

export const HOST_FORMAT = "cells.visualizer.host@1";
export const HOST_ELEMENT = "cells-host";
/** What a page with no profile has: as on the artifact. */
export const HOST_DEFAULTS = Object.freeze({ format: null, release: null, links: "hash", api: null, problem: null });
const LINKS = new Set(["hash", "query"]);

/** The profile a block's text gives: the defaults where there is no text, and where the text is not a profile. */
export function hostProfile(text) {
  if (text === null || text === undefined) return HOST_DEFAULTS;
  const wrong = (problem) => Object.freeze({ ...HOST_DEFAULTS, problem });
  let block;
  try {
    block = JSON.parse(text);
  } catch {
    return wrong("the host profile is not JSON");
  }
  if (!block || typeof block !== "object" || Array.isArray(block)) return wrong("the host profile is not an object");
  if (block.format !== HOST_FORMAT) return wrong(`the host profile's format is not ${HOST_FORMAT}`);
  if (block.release !== null && block.release !== undefined && typeof block.release !== "string") return wrong("the host profile's release is not a name");
  if (block.links !== undefined && !LINKS.has(block.links)) return wrong("the host profile's links is neither hash nor query");
  if (block.api !== null && block.api !== undefined && typeof block.api !== "string") return wrong("the host profile's api is not an address");
  // Within the format's major, what a reader does not know is left aside.
  return Object.freeze({ format: HOST_FORMAT, release: block.release ?? null, links: block.links ?? HOST_DEFAULTS.links, api: block.api ?? null, problem: null });
}

/** The profile of the page `root` belongs to (a document): its block, read once, or the defaults. */
export function readHost(root = globalThis.document) {
  let element = null;
  try {
    element = root?.getElementById?.(HOST_ELEMENT) ?? null;
  } catch {
    element = null;
  }
  if (!element) return HOST_DEFAULTS;
  if (String(element.getAttribute?.("type") || "").toLowerCase() !== "application/json") return Object.freeze({ ...HOST_DEFAULTS, problem: "the host profile is not a JSON block" });
  return hostProfile(element.textContent);
}
