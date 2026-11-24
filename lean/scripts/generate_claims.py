"""Generate claim notes, the README overview and the proof and evidence catalog."""

import argparse
import json
import os
import re
import stat
import sys
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory
from urllib.parse import quote

LANE = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/Eidosoma/Cells"
D351 = (
    f"{REPOSITORY}/blob/main/docs/DECISIONS.md#d351-the-wet-lab-gap-diagnosis-"
    "three-rows-confirmed-none-wrong-inside-its-claimed-domain-fr-55-goes-to-normal-the-user"
)
BEGIN = "<!-- generated: claims-index -->"
END = "<!-- /generated -->"
NOTE = "<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->"
COVERAGE_NOTE = "<!-- Generated from lean/registry.json and lean/claims.json. -->"
CLAIM_HEADER = "| Claim | Lean proof | Numerical check | Biological measurements and limits |"
PAIR_OUTCOMES = {
    "both_support": "Supported by both studies",
    "both_challenge": "Challenged by both studies",
    "different_results": "Different experimental results",
    "inconclusive": "Comparison unresolved",
    "not_independent": "Independent replication unconfirmed",
}
REPLAY_STATUS = {
    "missed": "Replay discrepancy",
    "reproduced": "Shared observable reproduced",
    "represented": "Representable with declared inputs",
    "partial": "Partial replay or missing inputs",
    "unconfirmed": "Replicated target unresolved",
    "pending": "Awaiting replay",
}


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


def check_sources(lane, since=None):
    """Compare the named input files with Git. Reading blobs leaves the shared index alone."""
    sys.path.insert(0, str(LANE.parent))
    try:
        from validation.source_snapshot import git
    finally:
        sys.path.pop(0)
    repo = lane.parent
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    register = json.loads((lane / "claims.json").read_text(), object_pairs_hook=unique_keys)
    base = None
    if since is not None:
        obj = git(repo, "rev-parse", "--verify", "--end-of-options", since + "^{commit}")
        base = obj.decode().strip()
    paths = defaultdict(lambda: defaultdict(set))
    for name, row in register["comparisons"].items():
        record = row["record_revision"]
        source = row["engine_revision"] if row["kind"] == "engine" else record
        inputs = [row["driver"], *row.get("record_inputs", {}).values()]
        for revision, targets in ((source, row["sources"].values()), (record, inputs)):
            if not re.fullmatch(r"[0-9a-f]{40}", revision):
                raise ValueError(f"{name}: invalid recorded revision {revision!r}")
            for target in targets:
                path, _ = source_path(target)
                paths[base or revision][str(path)].add(name)

    @cache
    def checkout_file(name):
        path = repo / name
        if path.parent.resolve() != path.parent:
            return None
        try:
            mode = path.lstat().st_mode
        except (FileNotFoundError, NotADirectoryError):
            return None
        if stat.S_ISLNK(mode):
            return b"120000", os.fsencode(path.readlink())
        if stat.S_ISREG(mode):
            return (b"100755" if mode & stat.S_IXUSR else b"100644"), path.read_bytes()
        return None

    @cache
    def blob(oid):
        return git(repo, "cat-file", "blob", oid)

    changed = defaultdict(set)
    for revision, cited in paths.items():
        entries = {}
        for line in git(repo, "ls-tree", "-z", revision, "--", *cited).split(b"\0"):
            if line:
                meta, filename = line.split(b"\t", 1)
                entries[os.fsdecode(filename)] = meta.split()
        for name, comparisons in cited.items():
            expected = None
            if name in entries:
                mode, kind, oid = entries[name]
                if kind == b"blob":
                    expected = mode, blob(oid)
                elif base is None:
                    raise ValueError(f"{name} is not a file at {revision}")
            elif base is None:
                raise ValueError(f"missing cited file {name} at {revision}")
            if checkout_file(name) != expected:
                for comparison in comparisons:
                    changed[comparison].add(name)
    if git(repo, "rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("checkout revision changed during the source comparison")
    claims = register["claims"]
    return {
        "checkout": head,
        "baseline": base or "recorded revisions",
        "comparisons": len(register["comparisons"]),
        "claims": len(claims),
        "changed_claims": sorted(
            c["id"] for c in claims if changed.keys() & set(c["numerical"]["comparisons"])
        ),
        "changed_comparisons": {key: sorted(files) for key, files in sorted(changed.items())},
    }


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
    links.extend(
        pinned_link(label, target, record)
        for label, target in check.get("record_inputs", {}).items()
    )
    links += [
        pinned_link("Comparison driver", check["driver"], record),
        pinned_link("Recorded result", check["record"], record),
    ]
    revisions = [f"[Evidence checkpoint {record[:12]}]({REPOSITORY}/commit/{record})"]
    if check["kind"] == "engine":
        revisions.insert(0, f"[Tested engine {source[:12]}]({REPOSITORY}/commit/{source})")
    lines = [f"**{kind}** {ids}".rstrip()]
    if check.get("operators"):
        lines.append("**Operators** " + ", ".join(f"`{op}`" for op in check["operators"]))
    return "\n\n".join([*lines, " · ".join(links), " · ".join(revisions)])


def publication_url(e):
    source = f"https://doi.org/{e['doi']}" if e.get("doi") else e["url"]
    if not source.startswith("https://"):
        raise ValueError(f"expected an HTTPS primary source for {e['dataset_id']}")
    return source


def publication_link(e):
    return f"[{e['citation']}]({publication_url(e)})"


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


def wet_lab_register(claims):
    groups = {outcome: [] for outcome in PAIR_OUTCOMES}
    replay_counts = Counter()
    misses = []
    seen = set()
    reviewed_claims = 0
    pending = []
    single_source = []
    for key, claim in claims.items():
        biology = claim["biology"]
        evidence = {e["dataset_id"]: e for e in biology["evidence"]}
        pairs = biology.get("pairs", [])
        claim_link = f"[{claim['title']}](claims/{key}.md#biological-evidence)"
        if not pairs:
            if len(evidence) >= 2:
                pending.append(claim_link)
            elif len(evidence) == 1:
                single_source.append(claim_link)
            continue
        reviewed_claims += 1
        if len(evidence) != len(biology["evidence"]):
            raise ValueError(f"{key}: ambiguous dataset ID in paired evidence")
        compared = set()
        for pair in pairs:
            pair_id, outcome, ids = pair["id"], pair["outcome"], pair["datasets"]
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", pair_id) or pair_id in seen:
                raise ValueError(f"{key}: invalid or repeated wet-lab comparison ID {pair_id!r}")
            seen.add(pair_id)
            if len(ids) != 2 or len(set(ids)) != 2 or not set(ids) <= evidence.keys():
                raise ValueError(f"{pair_id}: name two distinct datasets belonging to this claim")
            identifier = (pair["assumption"].strip().casefold(), frozenset(ids))
            if identifier in compared:
                raise ValueError(f"{pair_id}: repeated comparison for this assumption")
            compared.add(identifier)
            studies = [evidence[i] for i in ids]
            publications = {publication_url(e).split("#")[0].rstrip("/").lower() for e in studies}
            if outcome not in groups or (len(publications) < 2 and outcome != "not_independent"):
                raise ValueError(f"{pair_id}: invalid outcome for these publications")
            if not all(pair[k].strip() for k in ("assumption", "comparison", "independence")):
                raise ValueError(f"{pair_id}: missing assumption, measurements or independence")
            sources = " · ".join(publication_link(e) for e in studies)
            replay = pair.get("replay")
            state = replay["status"] if replay else "pending"
            note = replay["assessment"].strip() if replay else "Awaiting an engine comparison."
            studies_agree = outcome in ("both_support", "both_challenge")
            if state not in REPLAY_STATUS or not note:
                raise ValueError(f"{pair_id}: invalid Cells replay status or assessment")
            if (state in ("missed", "reproduced") and not studies_agree) or (
                state == "unconfirmed" and studies_agree
            ):
                raise ValueError(f"{pair_id}: replay status conflicts with the paired evidence")
            replay_counts[state] += 1
            if state == "missed":
                misses.append(f"- [{pair['assumption']}](#pair-{pair_id})")
            cells = [
                f'<a id="pair-{pair_id}"></a>{pair["assumption"]} {claim_link}',
                pair["comparison"],
                pair["independence"] + " " + sources,
                f"**{REPLAY_STATUS[state]}.** {note}",
            ]
            cells = [" ".join(c.splitlines()).replace("|", r"\|") for c in cells]
            groups[outcome].append("| " + " | ".join(cells) + " |")

    summary = (
        f"[Paired wet-lab evidence](WET_LAB_EVIDENCE.md) covers {reviewed_claims} of "
        f"{len(claims)} claims. Across {len(seen)} comparisons, two independent studies support "
        f"the stated assumption in {len(groups['both_support'])} and challenge it "
        f"in {len(groups['both_challenge'])}. "
        "[Cells replay results](WET_LAB_EVIDENCE.md#cells-replay-results) "
        f"flag {len(misses)} discrepancies. Of the original eight, D351 confirmed three "
        "findings and classified five as indications. It found no errors within the laws’ "
        f"stated domains. [D351 ruling on main]({D351})"
    )
    parts = [
        NOTE,
        "# Paired wet-lab evidence",
        "Each row names one Cells assumption and two public primary experimental records. "
        "A supporting pair requires independently collected data from separate research groups "
        "and a comparable observable. Direction, approximate scale and pointwise numerical "
        "agreement are identified separately. A study may inform several rows. The linked "
        "claim page identifies calibration data and gives the full biological verdict.",
        "| Outcome | Reviewed pairs |\n| --- | ---: |\n"
        + "\n".join(f"| {label} | {len(groups[k])} |" for k, label in PAIR_OUTCOMES.items()),
        "## Cells replay results",
        "The last column records what Cells predicts for the observable the studies share. "
        "A fitted input or a synthetic control establishes representability. A partial replay "
        "names the missing input or readout. Each claim links its source and numerical checks.",
        "| Cells result | Pairs |\n| --- | ---: |\n"
        + "\n".join(f"| {label} | {replay_counts[s]} |" for s, label in REPLAY_STATUS.items()),
    ]
    if misses:
        parts += [
            '<a id="replicated-observations-missed-by-the-tested-law"></a>',
            "### Observations missed in the tested replays",
            "D351 requires at least two independent labs to measure the same quantity on the "
            "same molecular system under comparable conditions to confirm a finding. Of the "
            "original eight discrepancies, three met that rule. Acidification shifts Kv1.5 "
            "activation toward more positive voltages, and the central estimates show POPC "
            "expands on warming. Both findings concern direction. For Cx43, the confirmed "
            "finding is the two-phase decay of junctional current. Five rows remained "
            "indications. The review found no errors within the laws’ stated domains. "
            f"[D351 definition and row-by-row ruling on main]({D351})",
            "\n".join(misses),
        ]
    for outcome, rows in groups.items():
        if rows:
            parts += [
                f"## {PAIR_OUTCOMES[outcome]}",
                "| Assumption and claim | Measurements and scope | Independence and sources | "
                "Cells replay |\n"
                "| --- | --- | --- | --- |\n" + "\n".join(rows),
            ]
    parts += [
        "## Awaiting paired review",
        f"Claims with at least two datasets awaiting their first paired review ({len(pending)}). "
        "Several datasets can come from one paper or measure different quantities.",
    ]
    if pending:
        parts.append("\n".join("- " + link for link in sorted(pending)))
    if single_source:
        parts += [
            "## Seeking a second dataset",
            f"<details><summary>Claims with one recorded dataset ({len(single_source)})</summary>",
            "\n".join("- " + link for link in sorted(single_source)),
            "</details>",
        ]
    return "\n\n".join(parts) + "\n", summary


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
    if pairs := biology.get("pairs"):
        parts.append(
            "\n".join(
                f"- [{p['assumption']}](../WET_LAB_EVIDENCE.md#pair-{p['id']}) "
                f"· {PAIR_OUTCOMES[p['outcome']]}"
                for p in pairs
            )
        )
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


def coverage(inventory, claims, comparisons, repo, category_sections, wet_lab_summary):
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
    failing = [
        f"- [{c['title']}](claims/{c['id']}.md#numerical-comparison)"
        for c in claims.values()
        if c["numerical"]["status"] == "failed"
    ]
    parts = [
        COVERAGE_NOTE,
        "# Proof and evidence catalog",
        "Choose a claim for its assumptions, theorems, numerical results and sources. "
        "Partial evidence covers a measured part of a claim. A result marked not assessable "
        "has too much uncertainty for a verdict. [Topic overview](README.md#proof-index) · "
        "[Registered laws](#registered-laws) · [Registered operators](#registered-operators)",
        wet_lab_summary,
        "## Failing numerical checks",
        "\n".join(failing) or "The register lists zero numerical failures.",
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
            f"Recorded numerical comparisons exercise {n_checked}. Each linked record names "
            "the property tested.",
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
    outputs[lane / "WET_LAB_EVIDENCE.md"], wet_lab_summary = wet_lab_register(claims)
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
        inventory, claims, register["comparisons"], lane.parent, sections, wet_lab_summary
    )
    readme = lane / "README.md"
    before, start, rest = readme.read_text(encoding="utf-8").partition(BEGIN)
    body, end, after = rest.partition(END)
    if not start or not end or BEGIN in rest or "<!-- generated:" in body:
        raise ValueError("expected one claims-index block in the Lean README")
    index = "\n\n".join([BEGIN, registry_summary, "\n".join(overview), wet_lab_summary, END])
    outputs[readme] = before + index + after
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
            generated_page = path.parent == directory or path.name in {
                "COVERAGE.md",
                "WET_LAB_EVIDENCE.md",
            }
            if generated_page and not old.startswith(marker + "\n"):
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report stale pages without writing")
    mode.add_argument(
        "--check-sources",
        action="store_true",
        help="report changes to cited source files and comparison drivers as JSON",
    )
    parser.add_argument("--since", metavar="REV", help="compare all cited files to REV")
    parser.add_argument(
        "--live-registry",
        action="store_true",
        help="read the active law and operator inventory from the Cells checkout",
    )
    try:
        args = parser.parse_args()
        if args.since is not None and not args.check_sources:
            parser.error("--since requires --check-sources")
        if args.check_sources:
            if args.live_registry:
                parser.error("--check-sources reads the claim register directly")
            report = check_sources(LANE, args.since)
            print(json.dumps(report, indent=2))
            sys.exit(int(bool(report["changed_comparisons"])))
        sys.exit(0 if generate(LANE, args.check, args.live_registry) else 1)
    except CalledProcessError as error:
        detail = os.fsdecode(error.stderr or b"").strip() or str(error)
        print(f"claims: Git could not read the comparison history: {detail}", file=sys.stderr)
        sys.exit(2)
    except (ImportError, OSError, ValueError, TypeError, KeyError) as error:
        print(f"claims: {error}", file=sys.stderr)
        sys.exit(2 if args.check_sources else 1)
