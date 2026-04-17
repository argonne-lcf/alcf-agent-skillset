---
# Copy this file to the appropriate category directory and fill in all fields.
title: "Short, Specific Skill Title"
category: systems          # systems | software | containers | jobs | storage | networking | ai-tools | iri | agents
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

- `../related-skill.md` — brief reason why it is related
- `https://docs.alcf.anl.gov/...` — canonical documentation
