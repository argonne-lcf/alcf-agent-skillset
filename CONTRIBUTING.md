# Contributing to ALCF Agent Skills

Thank you for contributing to the ALCF agent skills library. This guide covers everything
you need to know to add a new skill or update an existing one.

---

## Quick Start

1. Copy `SKILL_TEMPLATE.md` to the appropriate category directory (e.g., `jobs/my-new-skill.md`).
2. Fill in all frontmatter fields and body sections.
3. Install the pre-commit hook (see below).
4. Run `python scripts/build_registry.py` to regenerate the registry.
5. Verify your skill appears in `skills.yaml` and `INDEX.md`.
6. Open a pull request.

---

## Frontmatter Requirements

Every skill file must begin with a YAML frontmatter block enclosed in `---` delimiters.
All fields are required unless marked optional.

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Title-cased, concise, unique across the repo. |
| `category` | string | Exactly one of the nine valid values listed below. |
| `systems` | list | Which ALCF systems this skill applies to. |
| `tags` | list | Lowercase, hyphenated keywords for agent filtering. |
| `description` | string | One to two sentences written for an agent. Should answer: "should I load this skill right now?" |
| `last_verified` | string | `YYYY-MM` date of last manual verification. |
| `alcf_docs_url` | string | (Optional) Link to canonical ALCF documentation. |

### Valid `category` values

There are nine valid categories, listed alphabetically:

- `agents` -- behavioral rules and conventions for AI agents on ALCF systems
- `ai-tools` -- AI-related tooling, APIs, and inference infrastructure
- `containers` -- container building, conversion, and execution
- `iri` -- Integrated Research Infrastructure services and APIs
- `jobs` -- PBS job submission, scheduling, monitoring, and templates
- `networking` -- SSH access, tunneling, proxy configuration
- `software` -- modules, frameworks, compilers, and package installation
- `storage` -- file systems, data transfer, and storage best practices
- `systems` -- hardware overviews, architecture, and system-specific configuration

### Valid `systems` values

- `aurora` -- Intel GPU (Ponte Vecchio) supercomputer
- `polaris` -- NVIDIA A100 GPU supercomputer
- `all` -- use only if the skill genuinely applies to every ALCF system identically

---

## Tag Conventions

- Use **lowercase, hyphenated** terms (e.g., `pbs-job`, `ssh-tunnel`, `pytorch`).
- **Prefer existing tags** over creating new ones. Check `skills.yaml` for the current tag vocabulary before introducing a new tag.
- At minimum, include the category name and the primary technology or concept as tags.
- Tags drive agent filtering -- be specific enough that an agent can decide whether to load the skill based on tags alone.

---

## Body Structure

Every skill file must include the following sections, in order. Agents expect all six
sections to be present; do not omit any of them, even if a section only says "None."

### Purpose

Expand on the frontmatter description. Explain what problem the skill solves and what
an agent learns by loading it.

### Prerequisites

List any other skills, access requirements, or system state that must be in place.

### Key Facts

Bullet list of the most critical, agent-actionable facts. Each bullet should be one to
two sentences. This section should work as a standalone quick reference.

### Examples

Concrete, runnable examples with expected output where possible. Code blocks must
specify the shell or language.

### Common Pitfalls

What typically goes wrong and why. Use the format: "if you see X, it means Y, do Z."

### See Also

Links to related skills (use relative paths) and canonical ALCF documentation URLs.

---

## Accuracy Standard

- Include a `last_verified` date that you can stand behind. This should be a `YYYY-MM`
  string representing when you last confirmed the content is accurate on an actual ALCF
  system.
- The registry builder flags any skill with a `last_verified` date older than 180 days
  as stale. Plan to re-verify periodically.
- If you are unsure about any detail, note the uncertainty explicitly in the
  **Common Pitfalls** section rather than omitting the information.

---

## Pre-commit Hook Installation

Install the pre-commit hook to automatically rebuild the registry before each commit:

```bash
cp .github/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Once installed, the hook runs `python scripts/build_registry.py` and stages the
updated `skills.yaml` and `INDEX.md` automatically.

---

## PR Checklist

Before opening a pull request, verify the following:

- [ ] **Frontmatter complete** -- all required fields are present and valid.
- [ ] **Registry rebuilt and committed** -- ran `python scripts/build_registry.py` and
      committed the updated `skills.yaml` and `INDEX.md`.
- [ ] **No stale warnings introduced** -- your new skill has a current `last_verified`
      date and the builder produces no new warnings.
- [ ] **Examples tested on actual system** -- all commands and code examples have been
      verified on the target ALCF system (Aurora, Polaris, or both).
- [ ] **Body sections complete** -- all six required sections (Purpose, Prerequisites,
      Key Facts, Examples, Common Pitfalls, See Also) are present.
- [ ] **Tags reviewed** -- you checked `skills.yaml` for existing tags before creating
      new ones.
