# ALCF Agent Skills Repository — Build Plan

## Overview

Build a GitHub repository called `alcf-agent-skills` that serves as a structured, machine-readable
library of "skills" — contextual knowledge documents — that AI agents can use when interacting with
ALCF (Argonne Leadership Computing Facility) computing systems. The repo is designed so that agents
can efficiently discover and load only the skills relevant to their current task, rather than loading
the entire library into context.

---

## Goals

1. Provide a structured library of Markdown skill files covering ALCF systems, software, job
   submission, storage, containers, networking, and AI tooling.
2. Automatically generate a machine-readable registry (`skills.yaml`) and a human-readable index
   (`INDEX.md`) by scanning skill file frontmatter — no hand-editing of the registry.
3. Keep the registry fresh via a pre-commit hook and/or GitHub Actions CI workflow.
4. Establish clear contribution conventions so the library grows consistently.

---

## Repository Layout

Create the following directory and file structure. All paths are relative to the repo root.

```
alcf-agent-skills/
│
├── README.md
├── INDEX.md                          ← generated, do not edit by hand
├── skills.yaml                       ← generated, do not edit by hand
├── SKILL_TEMPLATE.md
├── CONTRIBUTING.md
│
├── scripts/
│   └── build_registry.py
│
├── .github/
│   ├── workflows/
│   │   └── build-registry.yml
│   └── hooks/
│       └── pre-commit
│
├── systems/
│   ├── aurora/
│   │   ├── overview.md
│   │   ├── filesystems.md
│   │   └── scheduler.md
│   ├── polaris/
│   │   ├── overview.md
│   │   ├── filesystems.md
│   │   └── scheduler.md
│   └── sunspot/
│       └── overview.md
│
├── software/
│   ├── modules/
│   │   ├── aurora-modules.md
│   │   └── polaris-modules.md
│   ├── frameworks/
│   │   ├── oneapi.md
│   │   ├── pytorch-aurora.md
│   │   └── pytorch-polaris.md
│   └── installation/
│       ├── pip-venv.md
│       ├── conda-mamba.md
│       └── spack.md
│
├── containers/
│   ├── concepts.md
│   ├── build-remote.md
│   ├── build-from-dockerhub.md
│   ├── aurora-container-run.md
│   └── polaris-container-run.md
│
├── jobs/
│   ├── pbs-basics.md
│   ├── monitoring.md
│   ├── aurora-templates/
│   │   ├── single-node-mpi.md
│   │   ├── multi-node-pytorch.md
│   │   └── interactive-session.md
│   └── polaris-templates/
│       ├── single-node-gpu.md
│       └── multi-node-pytorch.md
│
├── storage/
│   ├── lustre-best-practices.md
│   ├── eagle.md
│   └── data-transfer.md
│
├── networking/
│   ├── ssh-access.md
│   ├── ssh-tunneling.md
│   └── proxy-patterns.md
│
├── ai-tools/
│   ├── argo-api.md
│   ├── claude-code-on-polaris.md
│   └── inference-serving.md
│
└── agents/
    ├── safety.md
    ├── etiquette.md
    ├── error-recovery.md
    └── escalation.md
```

---

## Skill File Frontmatter Specification

Every skill file must begin with a YAML frontmatter block. The registry builder parses this block.
All fields are required unless marked optional.

```yaml
---
title: "Human-readable title of this skill"
category: systems | software | containers | jobs | storage | networking | ai-tools | agents
systems:
  - aurora        # list all applicable: aurora, polaris, sunspot, all
  - polaris
tags:
  - pbs           # lowercase, hyphenated, free-form keywords
  - scheduler
  - mpi
description: >
  One or two sentences describing what this skill covers and when an agent should load it.
  This text is included verbatim in the registry and used by agents for skill selection.
last_verified: "2026-03"          # YYYY-MM of last manual verification
alcf_docs_url: "https://..."      # optional: link to canonical ALCF documentation
---
```

### Field rules

- `title`: Title-cased, concise, unique across the repo.
- `category`: Must be exactly one of the eight listed values. Used for grouping in INDEX.md.
- `systems`: List. Use `all` only if the skill genuinely applies to every ALCF system identically.
- `tags`: At minimum include the category name and the primary technology/concept. Tags drive
  agent filtering — be specific.
- `description`: Written for an agent, not a human. Should answer "should I load this skill right
  now?" The build script surfaces this text in the registry.
- `last_verified`: Year-month string. The registry builder will warn if this is more than 6 months
  old relative to today.

---

## File: `scripts/build_registry.py`

This is the core automation script. Implement it as follows.

### Behavior

1. Walk the entire repository tree, skipping `scripts/`, `.github/`, and any file not ending in
   `.md`.
2. For each `.md` file found, attempt to parse its YAML frontmatter. Skip files with no frontmatter
   or missing required fields, printing a warning to stderr with the filename and missing fields.
3. Collect all successfully parsed skills into a list of records.
4. Sort the list: first by `category` alphabetically, then by `title` alphabetically within each
   category.
5. Write `skills.yaml` to the repo root.
6. Write `INDEX.md` to the repo root.
7. Print a summary line: `Built registry: N skills across K categories.`

### Stale skill detection

After parsing each skill, compare its `last_verified` date to today. If more than 180 days have
passed, append a `stale: true` field to that skill's registry entry and print a warning:
`WARNING: <path> last verified <date>, may be outdated.`

### `skills.yaml` structure

```yaml
# Auto-generated by scripts/build_registry.py — do not edit by hand.
# Regenerate with: python scripts/build_registry.py
generated: "2026-03-15T10:00:00"
skill_count: 32
skills:
  - title: "Aurora System Overview"
    path: "systems/aurora/overview.md"
    category: systems
    systems: [aurora]
    tags: [aurora, architecture, hardware, interconnect]
    description: >
      Covers Aurora's node architecture, GPU layout, Slingshot interconnect, and storage
      topology. Load before any Aurora-specific task.
    last_verified: "2026-03"
    stale: false
    alcf_docs_url: "https://docs.alcf.anl.gov/aurora/getting-started/"
  # ... more entries
```

### `INDEX.md` structure

Generate this file with the following sections in order:

1. A header block:
   ```markdown
   # ALCF Agent Skills Index
   > Auto-generated by `scripts/build_registry.py` — do not edit by hand.
   > Last built: 2026-03-15 | Skills: 32 | Categories: 8
   ```

2. A "How to Use" section explaining that agents should load `skills.yaml`, filter by `systems`
   and/or `tags`, then load the relevant skill files' full content into context.

3. One section per category, in alphabetical order. Each section lists skills as a Markdown table
   with columns: Title (linked to file), Systems, Tags, Description, Last Verified. Mark stale
   skills with a ⚠️ emoji in the title cell.

### CLI interface

```
python scripts/build_registry.py [--root PATH] [--warn-stale-days N]
```

- `--root`: Repo root path. Defaults to the directory containing the script's parent directory.
- `--warn-stale-days`: Days before a skill is considered stale. Default 180.

### Dependencies

Use only Python standard library: `pathlib`, `datetime`, `argparse`, `sys`, `re`. Parse YAML
frontmatter manually (split on `---` delimiters, use `re` for simple key extraction) OR use
`PyYAML` if available, with a graceful fallback message if not installed. Do not require any
third-party library unconditionally.

---

## File: `.github/workflows/build-registry.yml`

Create a GitHub Actions workflow that runs `build_registry.py` on every push to `main` and on
every pull request. If the registry files (`skills.yaml`, `INDEX.md`) differ from what is committed,
the workflow should fail with a clear message: "Registry is out of date. Run
`python scripts/build_registry.py` and commit the results."

Use the following structure:

```yaml
name: Build Registry

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build-registry:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run registry builder
        run: python scripts/build_registry.py
      - name: Check for uncommitted changes
        run: |
          git diff --exit-code skills.yaml INDEX.md || \
          (echo "Registry out of date. Run: python scripts/build_registry.py" && exit 1)
```

---

## File: `.github/hooks/pre-commit`

Create a shell script that can be installed as a Git pre-commit hook. When installed, it runs
`build_registry.py` before every commit and automatically stages any changes to `skills.yaml` and
`INDEX.md`.

```bash
#!/usr/bin/env bash
set -e
echo "Running ALCF skills registry builder..."
python scripts/build_registry.py
git add skills.yaml INDEX.md
echo "Registry updated and staged."
```

Include installation instructions in `CONTRIBUTING.md`:
```bash
cp .github/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## File: `SKILL_TEMPLATE.md`

This is the canonical template new contributors copy when creating a skill. Include the full
frontmatter block with all fields, explanatory comments, and a body structure agents expect.

```markdown
---
# Copy this file to the appropriate category directory and fill in all fields.
title: "Short, Specific Skill Title"
category: systems          # systems | software | containers | jobs | storage | networking | ai-tools | agents
systems:
  - aurora                 # aurora | polaris | sunspot | all
tags:
  - example-tag
description: >
  One or two sentences describing what this skill covers and when an agent should load it.
  Written for an agent: answer "should I load this right now?"
last_verified: "YYYY-MM"
alcf_docs_url: ""          # optional
---

## Purpose

Expand on the description. What problem does this skill solve? What does an agent learn by
loading it?

## Prerequisites

List any other skills, access requirements, or system state that must be in place before
the content of this skill is applicable.

## Key Facts

Bullet list of the most critical, agent-actionable facts. Keep each bullet to one or two
sentences. This section should be loadable as a standalone quick reference.

- Fact one.
- Fact two.

## Examples

Concrete, runnable examples with expected output where possible. Code blocks should specify
the shell or language.

```bash
# Example command
qsub -A my_project -q prod -l select=2 job.sh
```

Expected output:
```
12345.polaris-pbs-01.hsn.cm.polaris.alcf.anl.gov
```

## Common Pitfalls

What typically goes wrong and why. Written as "if you see X, it means Y, do Z."

## See Also

- `../related-skill.md` — brief reason why it's related
- `https://docs.alcf.anl.gov/...` — canonical documentation
```

---

## Seed Skill Files

Create the following skill files with realistic, accurate content. These seed files validate the
entire pipeline end-to-end and serve as worked examples for contributors.

### `systems/aurora/overview.md`

Cover: node count and type (Intel Blades, GPU count per node), Slingshot-11 interconnect, storage
mounts available on compute nodes (`/lus/flare`, `/home`, `/soft`), and the two login nodes
(`aurora-uan-0001`, `aurora-uan-0002`). Note that Aurora uses Intel Data Center GPU Max Series
(Ponte Vecchio). Include a Key Facts section with the most operationally important details: don't
compile on login nodes, use `module` to manage software, default shell is bash.

### `jobs/pbs-basics.md`

Cover: essential PBS commands (`qsub`, `qstat`, `qdel`, `qhold`, `qrls`), common `qsub` flags
(`-A`, `-q`, `-l select`, `-l walltime`, `-o`, `-e`, `-j oe`), how to read `qstat` output, job
states (Q, R, E, H, F), and how to check why a job is held. Include a minimal working job script
example. Note the difference between Polaris and Aurora queue names where they differ.

### `agents/etiquette.md`

Cover the rules agents must follow when operating on ALCF login nodes: do not run compute-intensive
work on login nodes (compilation of large projects, model inference, data preprocessing at scale);
do not submit more than a reasonable number of jobs in rapid succession without checking queue
status first; respect file system quotas and check usage before large writes; do not run persistent
background processes on login nodes without user awareness; prefer `qsub` interactive sessions for
anything that requires more than a few seconds of CPU. Also cover: what to do if a command hangs
(send SIGINT, do not kill -9 unless necessary), and how to check if a system is in maintenance
(`/etc/motd`, ALCF status page).

### `containers/build-remote.md`

Cover: why containers on ALCF use Apptainer (formerly Singularity) rather than Docker; how to
build a Docker image locally that targets Aurora's hardware (Intel GPU, oneAPI base images) or
Polaris's hardware (NVIDIA A100, CUDA base images); how to push to a registry; how to pull and
convert to `.sif` format on the login node using `apptainer pull` or `apptainer build`; and how
to run the container on a compute node via a PBS job script. Note the `--bind` flag for mounting
lustre paths, and the `--nv` flag for NVIDIA GPU passthrough on Polaris.

### `networking/ssh-tunneling.md`

Cover: the standard two-hop SSH path to reach internal ANL resources (bastion → login node);
how to set up a port forward through this chain for reaching internal APIs (e.g., `apps.inside.anl.gov`);
SSH ControlMaster configuration for sharing connections and reducing MFA prompts; common pitfalls
(stale ControlPath sockets, `too many authentication failures` when ControlMaster mux is broken);
and cleanup commands. Include concrete `~/.ssh/config` stanzas for both Aurora and Polaris access.

---

## File: `README.md`

Write a README that explains:

1. What this repo is and who it is for (AI agents and the humans who deploy them on ALCF systems).
2. How to use it as an agent: load `skills.yaml`, filter by system/tags, fetch relevant skill files.
3. How to use it as a human: browse `INDEX.md` on GitHub.
4. How to contribute a new skill: copy `SKILL_TEMPLATE.md`, fill in frontmatter, run the registry
   builder, open a PR.
5. How to install the pre-commit hook.
6. A brief note on staleness: skills are community-maintained; check `last_verified` and the
   `stale` flag.

---

## File: `CONTRIBUTING.md`

Write a contributing guide covering:

1. Frontmatter requirements (all fields, valid values for `category` and `systems`).
2. Tag conventions: use lowercase hyphenated terms; prefer existing tags over creating new ones;
   check `skills.yaml` for the current tag vocabulary before adding a new skill.
3. Body structure: Purpose, Prerequisites, Key Facts, Examples, Pitfalls, See Also — all sections
   are expected by agents; do not omit them.
4. Accuracy standard: include a `last_verified` date you can stand behind; if you're unsure, note
   it in the Pitfalls section.
5. Pre-commit hook installation.
6. PR checklist: frontmatter complete, registry rebuilt and committed, no stale warnings introduced,
   examples tested on the actual system.

---

## Build Order for Claude Code

Execute the build in this order to allow early validation:

1. Create repo root files: `README.md`, `CONTRIBUTING.md`, `SKILL_TEMPLATE.md`.
2. Create `scripts/build_registry.py` with full implementation.
3. Create `.github/workflows/build-registry.yml` and `.github/hooks/pre-commit`.
4. Create all seed skill files (five files listed above).
5. Run `python scripts/build_registry.py` to generate `skills.yaml` and `INDEX.md`.
6. Verify output: confirm all five seed skills appear in both output files, confirm category
   grouping is correct, confirm no stale warnings for the seed files.
7. Create the remaining stub skill files — these should have complete, accurate frontmatter but
   may have abbreviated body content (Key Facts only) as placeholders for future expansion.
8. Run `python scripts/build_registry.py` again and confirm final counts are correct.

---

## Acceptance Criteria

The build is complete when:

- [ ] `python scripts/build_registry.py` runs without errors from the repo root.
- [ ] `skills.yaml` contains an entry for every `.md` file in the repo that has valid frontmatter.
- [ ] `INDEX.md` contains a section for each category, with all skills listed and linked correctly.
- [ ] The five seed skill files have substantive, accurate content (not just placeholder text).
- [ ] The GitHub Actions workflow file is valid YAML and references the correct script path.
- [ ] The pre-commit hook installs and runs correctly on a test commit.
- [ ] `README.md` and `CONTRIBUTING.md` are complete and accurate.
- [ ] No Python third-party dependencies are required to run the registry builder.
