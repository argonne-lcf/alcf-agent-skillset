#!/usr/bin/env python3
"""
ALCF Agent Skills Registry Builder

Walks the repository tree, parses YAML frontmatter from skill .md files,
validates required fields, detects stale skills, and generates:
  - skills.yaml  (machine-readable registry)
  - INDEX.md     (human-readable index with tables per category)

Dependencies: Python standard library only.

Usage:
    python scripts/build_registry.py [--root PATH] [--warn-stale-days N]
"""

import argparse
import re
import sys
from datetime import datetime, date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = sorted([
    "agents",
    "ai-tools",
    "containers",
    "iri",
    "jobs",
    "networking",
    "software",
    "storage",
    "systems",
])

REQUIRED_FIELDS = ["title", "category", "systems", "tags", "description", "last_verified"]

SKIP_DIRS = {"scripts", ".github", ".git", "docs", "__pycache__"}
SKIP_FILES = {"README.md", "CONTRIBUTING.md", "SKILL_TEMPLATE.md", "DESIGN_PLAN.md", "INDEX.md"}

# ---------------------------------------------------------------------------
# Frontmatter parsing (stdlib only — no PyYAML)
# ---------------------------------------------------------------------------


def extract_frontmatter(text: str) -> str | None:
    """Return the raw YAML frontmatter string, or None if absent."""
    if not text.startswith("---"):
        return None
    # Find the closing '---' delimiter (must be on its own line after the first)
    end = text.find("\n---", 3)
    if end == -1:
        return None
    return text[3:end].strip()


def _parse_inline_list(value: str) -> list[str]:
    """Parse '[a, b, c]' into ['a', 'b', 'c']."""
    inner = value.strip().strip("[]")
    if not inner:
        return []
    return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]


def parse_frontmatter(raw: str) -> dict:
    """Parse a raw YAML frontmatter string into a dict.

    Handles:
    - Simple key: value pairs
    - Multiline scalars with > or |
    - List fields with '- item' syntax
    - Inline list fields with '[item1, item2]' syntax
    - Quoted and unquoted values
    - Comment lines starting with #
    """
    result: dict = {}
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip blank lines and comment-only lines
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        # Match a top-level key
        m = re.match(r"^(\w[\w-]*)\s*:\s*(.*)", line)
        if not m:
            i += 1
            continue

        key = m.group(1)
        rest = m.group(2).strip()

        # Remove trailing inline comments (only outside quotes)
        # Simple heuristic: if rest doesn't start with a quote, strip from first #
        if rest and not rest.startswith('"') and not rest.startswith("'"):
            comment_match = re.match(r"^(.*?)\s+#.*$", rest)
            if comment_match:
                rest = comment_match.group(1).strip()

        # Case 1: inline list  e.g.  systems: [aurora, polaris]
        if rest.startswith("["):
            result[key] = _parse_inline_list(rest)
            i += 1
            continue

        # Case 2: multiline scalar ( > or | )
        if rest in (">", "|"):
            block_lines = []
            i += 1
            while i < len(lines):
                bline = lines[i]
                # Continuation: indented lines
                if bline and (bline[0] == " " or bline[0] == "\t"):
                    block_lines.append(bline.strip())
                    i += 1
                elif bline.strip() == "":
                    # blank line inside block scalar
                    block_lines.append("")
                    i += 1
                else:
                    break
            result[key] = " ".join(l for l in block_lines if l).strip()
            continue

        # Case 3: value is empty — might be a list on subsequent lines
        if rest == "":
            # Peek ahead for list items
            items = []
            i += 1
            while i < len(lines):
                nline = lines[i]
                lm = re.match(r"^\s+-\s+(.*)", nline)
                if lm:
                    val = lm.group(1).strip().strip("'\"")
                    # Strip trailing comment
                    comment_match2 = re.match(r"^(.*?)\s+#.*$", val)
                    if comment_match2:
                        val = comment_match2.group(1).strip()
                    items.append(val)
                    i += 1
                elif nline.strip() == "" or nline.strip().startswith("#"):
                    i += 1
                else:
                    break
            if items:
                result[key] = items
            else:
                result[key] = ""
            continue

        # Case 4: simple scalar value
        val = rest.strip("'\"")
        result[key] = val
        i += 1

    return result


# ---------------------------------------------------------------------------
# Skill discovery and validation
# ---------------------------------------------------------------------------


def discover_skills(root: Path) -> list[tuple[Path, dict]]:
    """Walk root for .md files, parse frontmatter, return list of (path, metadata)."""
    skills = []
    for md_file in sorted(root.rglob("*.md")):
        rel = md_file.relative_to(root)

        # Skip excluded directories
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        # Skip excluded files
        if rel.name in SKIP_FILES:
            continue

        text = md_file.read_text(encoding="utf-8", errors="replace")
        raw_fm = extract_frontmatter(text)
        if raw_fm is None:
            continue

        meta = parse_frontmatter(raw_fm)

        # Validate required fields
        missing = [f for f in REQUIRED_FIELDS if f not in meta or meta[f] == "" or meta[f] == []]
        if missing:
            print(
                f"WARNING: {rel} — missing required fields: {', '.join(missing)}",
                file=sys.stderr,
            )
            continue

        # Validate category
        if meta["category"] not in VALID_CATEGORIES:
            print(
                f"WARNING: {rel} — invalid category '{meta['category']}' "
                f"(valid: {', '.join(VALID_CATEGORIES)})",
                file=sys.stderr,
            )
            continue

        # Normalize list fields (in case they were parsed as strings)
        for list_field in ("systems", "tags"):
            if isinstance(meta[list_field], str):
                meta[list_field] = [s.strip() for s in meta[list_field].split(",") if s.strip()]

        meta["path"] = str(rel)
        skills.append((rel, meta))

    return skills


def check_staleness(skills: list[tuple[Path, dict]], warn_days: int) -> None:
    """Set stale flag and emit warnings for skills older than warn_days."""
    today = date.today()
    for rel, meta in skills:
        lv = meta.get("last_verified", "")
        try:
            # Accept YYYY-MM or YYYY-MM-DD
            if re.match(r"^\d{4}-\d{2}$", lv):
                verified_date = datetime.strptime(lv, "%Y-%m").date()
            elif re.match(r"^\d{4}-\d{2}-\d{2}$", lv):
                verified_date = datetime.strptime(lv, "%Y-%m-%d").date()
            else:
                meta["stale"] = True
                print(
                    f"WARNING: {rel} — unparseable last_verified '{lv}'",
                    file=sys.stderr,
                )
                continue

            delta = (today - verified_date).days
            if delta > warn_days:
                meta["stale"] = True
                print(
                    f"WARNING: {rel} last verified {lv}, may be outdated.",
                    file=sys.stderr,
                )
            else:
                meta["stale"] = False
        except ValueError:
            meta["stale"] = True
            print(
                f"WARNING: {rel} — unparseable last_verified '{lv}'",
                file=sys.stderr,
            )


def sort_skills(skills: list[tuple[Path, dict]]) -> list[tuple[Path, dict]]:
    """Sort by category then title, both alphabetically."""
    return sorted(skills, key=lambda s: (s[1]["category"], s[1]["title"].lower()))


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------


def _yaml_list(items: list[str]) -> str:
    """Format a list as YAML inline: [a, b, c]."""
    return "[" + ", ".join(items) + "]"


def _yaml_escape(s: str) -> str:
    """Escape a string for safe YAML output."""
    # If the string contains characters that could be problematic, quote it
    if any(c in s for c in (":", "#", "'", '"', "\n", "[", "]", "{", "}", ",")):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f'"{s}"'


def write_skills_yaml(skills: list[tuple[Path, dict]], output: Path) -> None:
    """Write skills.yaml to output path."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    lines = [
        "# Auto-generated by scripts/build_registry.py \u2014 do not edit by hand.",
        "# Regenerate with: python scripts/build_registry.py",
        f'generated: "{now}"',
        f"skill_count: {len(skills)}",
    ]

    if skills:
        lines.append("skills:")
        for _, meta in skills:
            lines.append(f"  - title: {_yaml_escape(meta['title'])}")
            lines.append(f"    path: {_yaml_escape(meta['path'])}")
            lines.append(f"    category: {meta['category']}")
            lines.append(f"    systems: {_yaml_list(meta['systems'])}")
            lines.append(f"    tags: {_yaml_list(meta['tags'])}")
            # Write description as folded block scalar
            desc = meta.get("description", "").strip()
            lines.append(f"    description: >")
            # Wrap description at ~78 chars for readability
            indent = "      "
            words = desc.split()
            desc_line = ""
            for word in words:
                if desc_line and len(indent) + len(desc_line) + 1 + len(word) > 80:
                    lines.append(indent + desc_line)
                    desc_line = word
                else:
                    desc_line = (desc_line + " " + word).strip() if desc_line else word
            if desc_line:
                lines.append(indent + desc_line)
            lines.append(f'    last_verified: "{meta["last_verified"]}"')
            lines.append(f"    stale: {'true' if meta.get('stale') else 'false'}")
            if meta.get("alcf_docs_url"):
                lines.append(f'    alcf_docs_url: "{meta["alcf_docs_url"]}"')
    else:
        lines.append("skills: []")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_index_md(skills: list[tuple[Path, dict]], output: Path) -> None:
    """Write INDEX.md to output path."""
    now = datetime.now().strftime("%Y-%m-%d")
    categories = sorted(set(m["category"] for _, m in skills))

    lines = [
        "# ALCF Agent Skills Index",
        "",
        f"> Auto-generated by `scripts/build_registry.py` \u2014 do not edit by hand.",
        f"> Last built: {now} | Skills: {len(skills)} | Categories: {len(categories)}",
        "",
        "---",
        "",
        "## How to Use",
        "",
        "### For Agents",
        "",
        "1. Load `skills.yaml` from this repository.",
        "2. Filter skills by `systems` (e.g., `aurora`, `polaris`) and/or `tags` to find relevant skills.",
        "3. Fetch the full content of matching skill files (using the `path` field) into your context.",
        "4. Use the loaded skills to inform your responses about ALCF systems.",
        "",
        "### For Humans",
        "",
        "Browse the tables below to find skills by category. Click the title to view the full skill file.",
        "",
        "---",
        "",
    ]

    if not categories:
        lines.append("*No skills found. Add skill files with valid YAML frontmatter to populate this index.*")
        lines.append("")
    else:
        for cat in categories:
            cat_skills = [(r, m) for r, m in skills if m["category"] == cat]
            lines.append(f"## {cat.replace('-', ' ').title()}")
            lines.append("")
            lines.append("| Title | Systems | Tags | Description | Last Verified |")
            lines.append("|-------|---------|------|-------------|---------------|")
            for rel, meta in cat_skills:
                title = meta["title"]
                if meta.get("stale"):
                    title_cell = f"\u26a0\ufe0f [{title}]({meta['path']})"
                else:
                    title_cell = f"[{title}]({meta['path']})"
                systems_cell = ", ".join(meta["systems"])
                tags_cell = ", ".join(meta["tags"])
                desc = meta.get("description", "").strip()
                if len(desc) > 120:
                    desc = desc[:117] + "..."
                desc_cell = desc.replace("|", "\\|")
                lv_cell = meta["last_verified"]
                lines.append(f"| {title_cell} | {systems_cell} | {tags_cell} | {desc_cell} | {lv_cell} |")
            lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the ALCF Agent Skills registry from skill file frontmatter."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root path. Defaults to the parent of the scripts/ directory.",
    )
    parser.add_argument(
        "--warn-stale-days",
        type=int,
        default=180,
        help="Number of days before a skill is considered stale (default: 180).",
    )
    args = parser.parse_args()

    if args.root:
        root = args.root.resolve()
    else:
        # Default: parent of the directory containing this script
        root = Path(__file__).resolve().parent.parent

    if not root.is_dir():
        print(f"ERROR: Root path {root} is not a directory.", file=sys.stderr)
        sys.exit(1)

    # Discover and validate skills
    skills = discover_skills(root)

    # Check staleness
    check_staleness(skills, args.warn_stale_days)

    # Sort
    skills = sort_skills(skills)

    # Count categories
    categories = sorted(set(m["category"] for _, m in skills))

    # Write outputs
    write_skills_yaml(skills, root / "skills.yaml")
    write_index_md(skills, root / "INDEX.md")

    # Summary
    print(f"Built registry: {len(skills)} skills across {len(categories)} categories.")


if __name__ == "__main__":
    main()
