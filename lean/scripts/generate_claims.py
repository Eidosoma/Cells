"""Generate claim notes, the README overview and the proof and evidence catalog."""

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

LANE = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/Eidosoma/Cells"
BEGIN = "<!-- generated: claims-index -->"
END = "<!-- /generated -->"
NOTE = "<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->"
COVERAGE_NOTE = "<!-- Generated from lean/registry.json and lean/claims.json. -->"
CLAIM_HEADER = "| Claim | Lean proof | Numerical check | Biological measurements and limits |"


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def source_path(target):
    filename, _, anchor = target.partition("#")
    path = Path(filename)
    if not filename or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"expected a checkout-relative source, got {target!r}")
    return path, f"#{quote(anchor)}" if anchor else ""


def local_link(label, target, repo, from_dir="lean/claims"):
    """Register paths start at the checkout root."""
    path, fragment = source_path(target)
    file = (repo / path).resolve()
    if not file.is_relative_to(repo) or not file.is_file():
        raise ValueError(f"missing source {target!r}")
    if re.fullmatch(r"#L[0-9]+", fragment):
        if not 1 <= int(fragment[2:]) <= len(file.read_bytes().splitlines()):
            raise ValueError(f"line outside source {target!r}")
    relative = os.path.relpath(repo / path, repo / from_dir)
    return f"[{label}]({quote(Path(relative).as_posix())}{fragment})"


def pinned_link(label, target, revision):
    path, fragment = source_path(target)
    return f"[{label}]({REPOSITORY}/blob/{revision}/{quote(path.as_posix())}{fragment})"


def theorem_link(name, source, repo):
    path, _ = source_path(source)
    if not (repo / path).resolve().is_relative_to(repo):
        raise ValueError(f"expected a checkout-relative Lean file, got {source!r}")
    symbol = re.escape(name.rsplit(".", 1)[-1])
    declaration = re.compile(rf"\b(?:theorem|lemma)\s+(?:[\w.]+\.)?({symbol})(?=[\s:(]|$)")
    content = (repo / path).read_text(encoding="utf-8")
    matches = list(declaration.finditer(content))
    # Lean resolves the qualified name and module on a full build. Repeated
    # short names in different namespaces can share a source file.
    target = source
    if len(matches) == 1:
        line = content.count("\n", 0, matches[0].start(1)) + 1
        target = f"{source}#L{line}"
    return local_link(name, target, repo)


def status(value, allowed):
    if value not in allowed:
        raise ValueError(f"unknown status {value!r}, expected one of {', '.join(allowed)}")
    return value.replace("_", " ").capitalize()


def comparison_text(check):
    kind = {"engine": "Engine", "reference": "Reference calculation"}[check["kind"]]
    ids = ", ".join(f"`{item}`" for item in [*check["models"], *check["laws"]])
    record = check["record_revision"]
    source = check["engine_revision"] if check["kind"] == "engine" else record
    for revision in (record, source):
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError(f"invalid source revision {revision!r}")
    links = [pinned_link(label, target, source) for label, target in check["sources"].items()]
    links += [
        pinned_link("Comparison driver", check["driver"], record),
        pinned_link("Recorded result", check["record"], record),
    ]
    revisions = [f"[Evidence checkpoint {record[:12]}]({REPOSITORY}/commit/{record})"]
    if check["kind"] == "engine":
        revisions.insert(0, f"[Tested engine {source[:12]}]({REPOSITORY}/commit/{source})")
    lines = [f"**{kind}** {ids}"]
    if check.get("operators"):
        lines.append("**Operators** " + ", ".join(f"`{op}`" for op in check["operators"]))
    return "\n\n".join([*lines, " · ".join(links), " · ".join(revisions)])


def publication_link(e):
    source = f"https://doi.org/{e['doi']}" if e.get("doi") else e["url"]
    if not source.startswith("https://"):
        raise ValueError(f"expected an HTTPS primary source for {e['dataset_id']}")
    return f"[{e['citation']}]({source})"


def experiment_text(e, unit, repo):
    groups = [e.get(key, []) for key in ("fit", "evaluation", "excluded")]
    if e["role"] == "held_out_from_fitting":
        if not groups[1] or set(groups[0]) & set(groups[1]):
            raise ValueError(f"expected held-out evaluation conditions for {e['dataset_id']}")
    if set(groups[2]) & (set(groups[0]) | set(groups[1])):
        raise ValueError(f"excluded conditions were used for {e['dataset_id']}")
    lines = [
        f"### {e['dataset_id']}",
        "",
        f"{e['context']} {e['locator']} {publication_link(e)}",
        "",
        f"- **Evidence role** {e['role'].replace('_', ' ')}",
    ]
    for label, values in zip(("Fit", "Evaluation", "Excluded"), groups, strict=True):
        if values:
            lines.append(f"- **{label}** {', '.join(values)}")
    for key in ("observed", "predicted"):
        if key in e:
            lines.append(f"- **{key.title()}** {e[key]} {unit}")
    links = [local_link("Dataset manifest", e["manifest"], repo)]
    if "measurements" in e:
        links.append(local_link("Measurements", e["measurements"], repo))
    links.append(local_link("Comparison verdict", e["report"], repo))
    lines.extend(["", e["uncertainty"], "", e["assessment"] + " " + " · ".join(links)])
    return "\n".join(lines)


def biological_summary(biology, verdict):
    findings = [biology["finding"]] if biology.get("finding") else []
    for e in biology["evidence"]:
        values = [
            f"{name.title()} {e[name]} {biology['unit']}."
            for name in ("observed", "predicted")
            if name in e
        ]
        findings.append(" ".join([*values, e["assessment"], publication_link(e)]))
    if not findings:
        return f"**Measurement sought.** {biology['observable']}"
    label = "Partial evidence" if verdict == "Open" else verdict
    return f"**{label}.** " + " ".join(findings)


def render_claim(claim, claims, comparisons, repo):
    formal, numerical, biology = (claim[k] for k in ("formal", "numerical", "biology"))
    proof = status(formal["status"], ("proved", "open"))
    tested = status(numerical["status"], ("checked", "failed", "open"))
    empirical = status(
        biology["status"], ("open", "not_assessable", "supported", "disagrees", "mixed")
    )
    if bool(formal["theorems"]) != (proof == "Proved"):
        raise ValueError("proved claims need theorem references and open claims have none")
    if tested != "Open" and not numerical["comparisons"]:
        raise ValueError("a numerical result needs a comparison record")
    if empirical != "Open" and not biology["evidence"]:
        raise ValueError("an empirical verdict needs an experimental evidence record")

    parts = [NOTE, f"# {claim['title']}", claim["statement"]]
    if claim["assumptions"]:
        parts += ["## Assumptions", "\n".join(f"- {a}" for a in claim["assumptions"])]
    parts += ["## Lean proof", f"**{proof}**"]
    if formal["theorems"]:
        parts.append(
            "\n".join(
                "- " + theorem_link(name, source, repo)
                for name, source in formal["theorems"].items()
            )
        )
    if formal.get("about"):
        parts.append("Direct proof subject " + ", ".join(f"`{piece}`" for piece in formal["about"]))
    if sources := formal.get("sources"):
        links = [
            f"[{label}]({path})" if path.startswith("https://") else local_link(label, path, repo)
            for label, path in sources.items()
        ]
        parts.append("Proof sources " + " · ".join(links))
    if claim.get("uses"):
        parts.append("Uses " + " · ".join(f"[{claims[i]['title']}]({i}.md)" for i in claim["uses"]))
    parts += ["## Numerical comparison", f"**{tested}.** {numerical['result']}"]
    parts.extend(comparisons[i] for i in numerical["comparisons"])
    parts += ["## Biological evidence", f"**{empirical}.** {biology['observable']}"]
    if finding := biology.get("finding"):
        parts.append(finding)
    parts.append(f"**Unit** {biology['unit']}")
    parts.extend(experiment_text(e, biology["unit"], repo) for e in biology["evidence"])
    parts.append("[Claim index](../README.md#proof-index) · [Editable register](../claims.json)")
    title = claim["title"].replace("|", r"\|")
    summary = " ".join(biological_summary(biology, empirical).splitlines()).replace("|", r"\|")
    row = f"| [{title}](claims/{claim['id']}.md) | {proof} | {tested} | {summary} |"
    return "\n\n".join(parts) + "\n", row


def live_inventory(lane):
    """Keep only the data needed to reproduce coverage in a Lean-only checkout."""
    sys.path.insert(0, str(lane.parent / "src"))
    try:
        from cells.registry import declarations

        manifest = declarations.manifest()
    finally:
        sys.path.pop(0)
    if manifest["kind"] != "cells.declarations@2":
        raise ValueError(f"unsupported engine declarations format {manifest['kind']!r}")
    return {
        kind: {
            p["id"]: f"{p['module_path']}#L{p['line']}"
            for p in manifest["pieces"]
            if p["piece"] == kind
        }
        for kind in ("law", "operator")
    }


def coverage(inventory, claims, comparisons, repo, category_sections):
    direct, exercised = {}, {}
    for claim in claims.values():
        for piece in claim["formal"].get("about", []):
            if claim["formal"]["status"] != "proved":
                raise ValueError(f"{claim['id']}: direct coverage requires a proved claim")
            label = claim["title"].replace("|", r"\|")
            direct.setdefault(piece, []).append(f"[{label}](claims/{claim['id']}.md)")
    for key, record in comparisons.items():
        if record["kind"] != "engine":
            continue
        for kind in ("law", "operator"):
            for spelling in record.get(kind + "s", []):
                piece = spelling if "." in spelling else "cells." + spelling
                if any(piece in rows for other, rows in inventory.items() if other != kind):
                    raise ValueError(f"{key}: {piece} is classified under the wrong registry type")
                link = pinned_link(key, record["record"], record["record_revision"])
                exercised.setdefault(piece, []).append(link)
    active = set(inventory["law"]) | set(inventory["operator"])
    if unknown := direct.keys() - active - exercised.keys():
        raise ValueError(f"unrecognized direct proof subjects: {', '.join(sorted(unknown))}")
    parts = [
        COVERAGE_NOTE,
        "# Proof and evidence catalog",
        "Choose a claim for its assumptions, theorems, numerical results and sources. "
        "Partial evidence covers a measured part of a claim. A result marked not assessable "
        "has too much uncertainty for a verdict. [Topic overview](README.md#proof-index) · "
        "[Registered laws](#registered-laws) · [Registered operators](#registered-operators)",
        *category_sections,
    ]
    overview = []
    for kind in ("law", "operator"):
        rows = inventory[kind]
        n_direct = sum(key in direct for key in rows)
        n_checked = sum(key in exercised for key in rows)
        overview.append(f"[{n_direct} of {len(rows)} {kind}s](COVERAGE.md#registered-{kind}s)")
        parts += [
            f"## Registered {kind}s",
            f"Direct Lean claims cover {n_direct} of {len(rows)} registered {kind}s. "
            f"Recorded numerical comparisons exercise {n_checked}. A run can exercise a "
            f"{kind} while checking a different property.",
        ]
        table = [
            f"| {kind.title()} | Direct Lean claims | Recorded comparisons |",
            "| --- | --- | --- |",
        ]
        for piece, target in sorted(rows.items()):
            label = local_link(f"`{piece}`", target, repo, from_dir="lean")
            proofs = " · ".join(direct.get(piece, [])) or "Open"
            runs = " · ".join(exercised.get(piece, [])) or "Open"
            table.append(f"| {label} | {proofs} | {runs} |")
        parts.append("\n".join(table))
    return "\n\n".join(parts) + "\n", "Direct Lean claims cover " + " and ".join(overview) + "."


def render(lane, live_registry=False):
    register = json.loads(
        (lane / "claims.json").read_text(encoding="utf-8"), object_pairs_hook=unique_keys
    )
    if type(register["version"]) is not int or register["version"] != 1:
        raise ValueError("unsupported claims register version")
    claims = {}
    for claim in register["claims"]:
        key = claim["id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key) or key in claims:
            raise ValueError(f"invalid or duplicate claim ID {key!r}")
        claims[key] = claim
    comparisons = {key: comparison_text(check) for key, check in register["comparisons"].items()}
    inventory_path = lane / "registry.json"
    inventory = (
        live_inventory(lane)
        if live_registry
        else json.loads(inventory_path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    )
    # A version-one register written before categories were introduced still renders.
    categories = register.get("categories", {"all": "All claims"})
    if not categories or any(
        not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key) for key in categories
    ):
        raise ValueError("category IDs must be nonempty, stable link fragments")
    groups = {key: [] for key in categories}
    proof_topics = {law: set() for law in inventory["law"]}
    outputs = {}
    if live_registry:
        outputs[inventory_path] = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    for key, claim in claims.items():
        try:
            note, row = render_claim(claim, claims, comparisons, lane.parent)
        except (KeyError, ValueError, TypeError) as error:
            raise ValueError(f"claim {key!r}: {error}") from error
        outputs[lane / "claims" / f"{key}.md"] = note
        category = claim.get("category", "all")
        if category not in groups:
            raise ValueError(f"claim {key!r} needs a category from the register")
        groups[category].append((claim, row))
        for subject in claim["formal"].get("about", []):
            if subject in proof_topics:
                proof_topics[subject].add(category)

    # A law usually gets its topic from its first direct proof. An explicit topic also
    # lets an open law appear here before there is a claim or biological measurement.
    assigned = register.get("law_categories", {})
    if assigned.keys() - proof_topics.keys() or set(assigned.values()) - groups.keys():
        raise ValueError("law_categories must name registered laws and existing categories")
    laws_by_topic = {}
    for law, topics in proof_topics.items():
        if law not in assigned and len(topics) > 1:
            raise ValueError(f"assign {law} a primary category in law_categories")
        topic = assigned.get(law) or next(iter(topics), None)
        groups.setdefault(topic, [])
        laws_by_topic.setdefault(topic, {})[law] = bool(topics)

    overview = [
        "| Category | Registered laws with proof | Claims with proof | Numerical checks "
        "| Claims with biological evidence |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    sections = []
    for key, group in groups.items():
        laws = laws_by_topic.get(key, {})
        if not (group or laws):
            continue
        title = categories[key] if key is not None else "Laws awaiting a category"
        anchor = "category-" + key if key is not None else "uncategorized-laws"
        counts = Counter(c["numerical"]["status"] for c, _ in group)
        checks = " · ".join(f"{counts[s]} {s}" for s in ("checked", "failed", "open") if counts[s])
        proved = sum(c["formal"]["status"] == "proved" for c, _ in group)
        measured = sum(
            bool(c["biology"].get("finding") or c["biology"]["evidence"]) for c, _ in group
        )
        law_count = f"{sum(laws.values())} of {len(laws)}" if laws else "—"
        claim_count = f"{proved} of {len(group)}" if group else "—"
        overview.append(
            f"| [{title}](COVERAGE.md#{anchor}) | {law_count} | {claim_count} "
            f"| {checks or '—'} | {measured} |"
        )
        sections.extend([f'<a name="{anchor}"></a>', f"## {title}"])
        pending = [
            local_link(f"`{law}`", inventory["law"][law], lane.parent, from_dir="lean")
            for law in sorted(laws)
            if not laws[law]
        ]
        if pending:
            sections.append("**Awaiting a direct Lean proof** " + " · ".join(pending))
        if group:
            sections.append(
                "\n".join(
                    [
                        CLAIM_HEADER,
                        "| --- | --- | --- | --- |",
                        *(row for _, row in group),
                    ]
                )
            )
    outputs[lane / "COVERAGE.md"], registry_summary = coverage(
        inventory, claims, register["comparisons"], lane.parent, sections
    )
    readme = lane / "README.md"
    before, start, rest = readme.read_text(encoding="utf-8").partition(BEGIN)
    body, end, after = rest.partition(END)
    if not start or not end or BEGIN in rest or "<!-- generated:" in body:
        raise ValueError("expected one claims-index block in the Lean README")
    outputs[readme] = (
        before + "\n\n".join([BEGIN, registry_summary, "\n".join(overview), END]) + after
    )
    return outputs


def generate(lane, check=False, live_registry=False):
    outputs = render(lane, live_registry)
    directory = lane / "claims"
    if directory.is_symlink():
        raise ValueError("the claim notes directory is a symbolic link")
    changed = []
    for path, content in outputs.items():
        if path.is_symlink():
            raise ValueError(f"refusing to replace a symbolic link at {path.name}")
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old is not None:
            marker = COVERAGE_NOTE if path == lane / "COVERAGE.md" else NOTE
            if (path.parent == directory or path == lane / "COVERAGE.md") and not old.startswith(
                marker + "\n"
            ):
                raise ValueError(f"handwritten file occupies generated path {path.name}")
        if old != content:
            changed.append(path)
    obsolete = [
        path
        for path in sorted(directory.glob("*.md"))
        if path not in outputs
        and not path.is_symlink()
        and path.read_text(encoding="utf-8").startswith(NOTE + "\n")
    ]
    if check:
        for path in [*changed, *obsolete]:
            print(f"stale generated documentation: {path.relative_to(lane)}", file=sys.stderr)
        return not (changed or obsolete)
    for path in changed:
        path.parent.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=path.parent) as tmp:
            draft = Path(tmp) / path.name
            draft.write_text(outputs[path], encoding="utf-8")
            draft.replace(path)
    for path in obsolete:
        path.unlink(missing_ok=True)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report stale pages without writing")
    parser.add_argument(
        "--live-registry",
        action="store_true",
        help="read the active law and operator inventory from the Cells checkout",
    )
    try:
        args = parser.parse_args()
        sys.exit(0 if generate(LANE, args.check, args.live_registry) else 1)
    except (ImportError, OSError, ValueError, TypeError, KeyError) as error:
        sys.exit(f"claims: {error}")
