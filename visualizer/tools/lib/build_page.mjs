// Builds the one page that every delivery mode uses: the local server, the
// standalone file and the artifact all get this same HTML.

import { build } from "esbuild";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const THREE_VERSION = "0.170.0";
// Published pages may load scripts only from a short list of CDNs; cdnjs is the preferred one.
export const THREE_CDN = `https://cdnjs.cloudflare.com/ajax/libs/three.js/${THREE_VERSION}/three.module.min.js`;
export const THREE_LOCAL = "/vendor/three.module.min.js";
export const DEFAULT_SCENE = path.join(ROOT, "data", "architecture", "architecture.scene.json");
// Generated replays (schema/RUN_VIEW.md, "Packaged for the viewer"). Never committed.
export const DEFAULT_RUNS = path.join(ROOT, "out", "runs");

/** The catalogue of adapted runs, or null when there is none. */
export async function readReplays(runsDir = DEFAULT_RUNS) {
  try {
    const index = JSON.parse(await readFile(path.join(runsDir, "index.json"), "utf8"));
    return index.runs?.length ? index : null;
  } catch {
    return null;
  }
}

// The document the artifact service wraps around a published page (read back from a
// published artifact on 14 November 2026). Local previews use the same wrapper.
const SKELETON_HEAD =
  '<meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">' +
  "<style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}" +
  "html{scroll-padding-top:env(safe-area-inset-top,0px)}body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}" +
  "img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style>";

/** The page content, as published: no doctype, html, head or body tags of its own. */
export async function buildPage({ scenePath = DEFAULT_SCENE, three = THREE_CDN, runsDir = DEFAULT_RUNS, inlineRuns = false } = {}) {
  const bundle = await build({
    entryPoints: [path.join(ROOT, "src", "main.js")],
    bundle: true,
    format: "esm",
    target: "es2022",
    write: false,
    minify: false,
    legalComments: "none",
    plugins: [
      {
        name: "three-from-url",
        setup(api) {
          api.onResolve({ filter: /^three$/ }, () => ({ path: three, external: true }));
        },
      },
    ],
  });
  const script = bundle.outputFiles[0].text.replaceAll("</script", "<\\/script");
  const data = JSON.parse(await readFile(scenePath, "utf8"));
  const replays = await readReplays(runsDir);
  if (replays) data.replays = replays;
  const scene = JSON.stringify(data).replaceAll("<", "\\u003c");
  // A page that cannot fetch (a file opened from disk) carries its runs inline.
  let inline = "";
  if (replays && inlineRuns) {
    for (const run of replays.runs) {
      const text = (await readFile(path.join(runsDir, path.basename(run.file)), "utf8")).replaceAll("<", "\\u003c");
      inline += `\n<script type="application/json" data-replay="${run.id}">${text}</script>`;
    }
  }
  const css = await readFile(path.join(ROOT, "src", "page.css"), "utf8");
  const template = await readFile(path.join(ROOT, "src", "page.html"), "utf8");
  return template
    .replace("/*__PAGE_CSS__*/", () => css.trim())
    .replace("__SCENE__", () => scene)
    .replace("<!--__RUNS__-->", () => inline)
    .replace("/*__BUNDLE__*/", () => script.trim());
}

/** The page as a complete document, for a file on disk or the local server. */
export function wrap(content, { theme = null, head = "" } = {}) {
  const attribute = theme ? ` data-theme="${theme}"` : "";
  return `<!doctype html><html${attribute}><head>${SKELETON_HEAD}${head}</head><body>\n${content}\n</body></html>\n`;
}

/** A Content-Security-Policy close to the artifact frame's, so a blocked load shows up locally. */
export function contentSecurityPolicy({ local = false } = {}) {
  const scripts = ["'unsafe-inline'", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net/npm/", "https://unpkg.com", "https://cdn.tailwindcss.com", "https://code.jquery.com"];
  if (local) scripts.push("'self'");
  return [
    "default-src 'none'",
    `script-src ${scripts.join(" ")}`,
    "style-src 'unsafe-inline' https://fonts.googleapis.com",
    "font-src https://fonts.gstatic.com data:",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "worker-src 'self' blob:",
  ].join("; ");
}
