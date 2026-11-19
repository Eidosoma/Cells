// What `git status --porcelain` says of a checkout, read for the page's tools (the click runner's record of a run, the
// stills' record): the lines that are changes of the page. A checkout whose node_modules is a link shows it as
// untracked, because the ignore rule names a folder; that line is no change of the page, wherever the folder stands.

/** The lines of a porcelain status that are changes: every line but an untracked node_modules. Null in, null out. */
export function changedLines(status) {
  if (status === null || status === undefined) return null;
  return String(status)
    .split("\n")
    .filter((line) => line.trim() && !/(^|[ /])node_modules\/?$/.test(line));
}

/** Whether a porcelain status shows uncommitted changes of the page; null where the status could not be read. */
export function hasChanges(status) {
  const lines = changedLines(status);
  return lines === null ? null : lines.length > 0;
}
