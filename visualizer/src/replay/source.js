// Getting one run into the page, as schema/RUN_VIEW.md fixes it ("Packaged for the
// viewer"): the run is inline in the page, or it is fetched from beside the page.

import { Run, validateReplay, PART_FORMAT } from "./run.js";

/** Base64 text to bytes, in a browser or in Node. */
export function decodeBase64(text) {
  if (typeof atob === "function") {
    const binary = atob(text);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
    return bytes.buffer;
  }
  const buffer = Buffer.from(text, "base64");
  return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
}

/** A run file (parsed JSON) as a Run. Throws with the first problems found if it breaks the contract. */
export function openReplay(file, entry = null) {
  const problems = validateReplay(file);
  if (problems.length) throw new Error(`the run file does not follow the replay format: ${problems.slice(0, 3).join("; ")}`);
  const buffer = decodeBase64(file.payload.data);
  if (buffer.byteLength !== file.payload.byte_length) {
    throw new Error(`the run's arrays are ${buffer.byteLength} bytes long, not the ${file.payload.byte_length} stated`);
  }
  return new Run(file.view, buffer, entry);
}

/**
 * Load the run a catalogue entry names. It is looked for in the page first
 * (<script type="application/json" data-replay="id">), then fetched from `entry.file`,
 * a URL relative to the page.
 */
export async function loadRun(entry, { root = globalThis.document, fetcher = globalThis.fetch } = {}) {
  let file = null;
  const inline = root?.querySelector?.(`script[type="application/json"][data-replay="${entry.id}"]`);
  if (inline) {
    file = JSON.parse(inline.textContent);
  } else {
    if (!entry.file) throw new Error("the catalogue gives no file for this run");
    if (typeof fetcher !== "function") throw new Error("this page cannot fetch the run");
    const response = await fetcher(entry.file);
    if (!response.ok) throw new Error(`${entry.file} answered ${response.status}`);
    file = await response.json();
  }
  const run = openReplay(file, entry);
  if (run.id !== entry.id) throw new Error(`the file holds run ${run.id}, not ${entry.id}`);
  return run;
}

/**
 * Fetch one part of a run: records that come in a file of their own beside the run's, so
 * that the run's own file stays small (schema/QUANTITY_LAYERS.md, rule 10). It is looked
 * for in the page first (<script type="application/json" data-replay-part="run-id/part">),
 * then fetched from the part's `file`. Resolves when its records can be read.
 */
export async function loadPart(run, partId, { root = globalThis.document, fetcher = globalThis.fetch } = {}) {
  const part = run.parts.get(partId);
  if (!part) throw new Error(`the run has no part ${partId}`);
  if (part.loaded) return run;
  if (part.loading) return part.loading;
  part.loading = (async () => {
    let file = null;
    const inline = root?.querySelector?.(`script[type="application/json"][data-replay-part="${run.id}/${partId}"]`);
    if (inline) {
      file = JSON.parse(inline.textContent);
    } else {
      if (typeof fetcher !== "function") throw new Error("this page cannot fetch the run's records");
      const response = await fetcher(part.file);
      if (!response.ok) throw new Error(`${part.file} answered ${response.status}`);
      file = await response.json();
    }
    if (file?.format !== PART_FORMAT) throw new Error(`the file is ${file?.format}, not ${PART_FORMAT}`);
    if (file.run !== run.id || file.part !== partId) throw new Error(`the file holds ${file.part} of run ${file.run}, not ${partId} of ${run.id}`);
    if (file.payload?.encoding !== "base64" || typeof file.payload.data !== "string") throw new Error("its arrays must be base64");
    run.attach(partId, decodeBase64(file.payload.data));
    return run;
  })();
  try {
    return await part.loading;
  } finally {
    part.loading = null;
  }
}
