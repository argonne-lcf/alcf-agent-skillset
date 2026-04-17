# ALCF Agent Skills

A structured, machine-readable library of "skills" -- contextual knowledge documents --
for AI agents operating on Argonne Leadership Computing Facility (ALCF) systems
(Aurora, Polaris). The repository is designed so that agents can efficiently discover
and load only the skills relevant to their current task, rather than pulling the entire
library into context.

---

## What Is a Skill?

A skill is a Markdown file with YAML frontmatter containing structured metadata
(title, category, systems, tags, description) and a standardized body
(Purpose, Prerequisites, Key Facts, Examples, Common Pitfalls, See Also).
Skills cover topics such as job submission, container workflows, SSH tunneling,
system architecture, and AI tooling on ALCF systems.

---

## For Agents

Agents consume this repository through the machine-readable registry:

1. **Load** `skills.yaml` from the repository root.
2. **Filter** skills by `systems` (e.g., `aurora`, `polaris`) and/or `tags`
   to find skills relevant to the current task.
3. **Fetch** the full content of matching skill files using the `path` field
   in each registry entry.
4. **Use** the loaded skills to inform responses about ALCF systems.

The registry includes a `description` field for each skill, written specifically
for agents, so you can decide whether to load a skill before reading the full file.

---

## For Humans

Browse `INDEX.md` on GitHub for a categorized, searchable table of all available
skills. Each skill title links directly to its source file.

---

## How to Contribute

1. **Copy** `SKILL_TEMPLATE.md` to the appropriate category directory
   (e.g., `jobs/my-new-skill.md`).
2. **Fill in** all frontmatter fields and body sections. See `CONTRIBUTING.md`
   for detailed requirements.
3. **Install** the pre-commit hook (see below).
4. **Run** `python scripts/build_registry.py` to regenerate `skills.yaml`
   and `INDEX.md`.
5. **Verify** your skill appears correctly in both generated files.
6. **Open** a pull request.

See `CONTRIBUTING.md` for the full contributing guide, including frontmatter
field specifications, tag conventions, body structure requirements, and the
PR checklist.

---

## Pre-commit Hook

Install the pre-commit hook to automatically rebuild the registry before each
commit:

```bash
cp .github/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Once installed, the hook runs `python scripts/build_registry.py` and stages
any changes to `skills.yaml` and `INDEX.md` so they stay in sync with skill
files.

---

## Staleness

Skills are community-maintained. Each skill carries a `last_verified` field
indicating the year and month it was last confirmed accurate on an actual ALCF
system. The registry builder flags skills older than 180 days as stale
(`stale: true` in `skills.yaml`).

When using a skill, check the `last_verified` date and the `stale` flag.
Stale skills may contain outdated commands, paths, or procedures. If you find
inaccuracies, please update the skill and submit a PR.

---

## Repository Layout

```
alcf-agent-skills/
  README.md               -- this file
  CONTRIBUTING.md          -- contribution guide
  SKILL_TEMPLATE.md        -- copy-and-fill template for new skills
  INDEX.md                 -- generated human-readable index (do not edit)
  skills.yaml              -- generated machine-readable registry (do not edit)
  scripts/
    build_registry.py      -- registry builder script
  .github/
    workflows/
      build-registry.yml   -- CI workflow to verify registry freshness
    hooks/
      pre-commit           -- pre-commit hook for local development
  systems/                 -- system architecture and configuration skills
  software/                -- modules, frameworks, and installation skills
  containers/              -- container build and run skills
  jobs/                    -- PBS job submission and template skills
  storage/                 -- file system and data transfer skills
  networking/              -- SSH, tunneling, and proxy skills
  ai-tools/                -- AI tooling and inference skills
  iri/                     -- Integrated Research Infrastructure skills
  agents/                  -- agent behavioral rules and conventions
```
