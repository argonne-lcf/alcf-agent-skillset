---
title: "Agent Etiquette on ALCF Systems"
category: agents
systems:
  - all
tags:
  - agents
  - etiquette
  - login-nodes
  - best-practices
description: >
  Rules agents must follow when operating on ALCF systems. Covers login node
  restrictions, job submission courtesy, filesystem awareness, and how to handle
  hung commands. Load at the start of any ALCF session.
last_verified: "2026-04"
---

## Purpose

Prevent AI agents from disrupting shared ALCF resources. These rules protect other users, system stability, and the agent's own reputation.

## Prerequisites

None — load this skill first in any ALCF interaction.

## Key Facts

### Login Node Rules

- Do NOT run compute-intensive work on login nodes: large compilations, model inference, data preprocessing at scale, or long-running computations.
- Login nodes are shared by many users. Heavy processes get noticed and may be killed by admins.
- For anything requiring more than a few seconds of CPU, use `qsub -I` to get an interactive compute session.
- No GPUs are available on login nodes (both Aurora and Polaris).

### Job Submission Courtesy

- Check queue status before submitting: `qstat -u $USER`
- Debug queue allows only 1 job per user at a time (both Aurora and Polaris).
- Do not submit more than a reasonable number of jobs without reviewing queue status.
- When using IRI API: wait at least 30 seconds between sequential debug queue submissions.
- Add `time.sleep(3)` between IRI write-script and run jobs for filesystem sync.

### Filesystem Awareness

- Check filesystem quota before large writes: `lfs quota -u $USER /home` or `lfs quota -u $USER /lus/flare`
- Home directory quota is 50 GB on both systems.
- Eagle filesystem (Polaris) is NOT backed up.
- DAOS (Aurora) is scratch storage that can disappear at any time.

### Process Management

- Do NOT run persistent background processes on login nodes without explicit user awareness.
- If a command hangs: send SIGINT (Ctrl-C) first. Only use `kill -9` if SIGINT fails and the process is truly stuck.
- Always verify job output before declaring success — check BOTH stdout and stderr.

### System Awareness

- Check system maintenance status: read `/etc/motd` on login.
- Check ALCF status page for planned maintenance windows.
- Node failures are common on Aurora — always implement checkpointing for long jobs.

## Examples

```bash
# Check queue before submitting
qstat -u $USER

# Interactive session instead of running on login node
qsub -I -A myproject -q debug -l select=1 -l walltime=01:00:00 -l filesystems=home

# Check filesystem quota
lfs quota -u $USER /home

# Check system status
cat /etc/motd
```

```python
# IRI API courtesy pattern
import time

write_job = polaris.submit(...)
write_job.wait(timeout=600, poll_interval=10)
time.sleep(3)   # filesystem sync

run_job = polaris.submit(...)
run_job.wait(timeout=1800, poll_interval=15)
time.sleep(5)   # let output files settle before reading
```

## Common Pitfalls

- Submitting to debug queue before previous job completes — job rejected.
- Running GPU builds on login nodes — fails (no GPUs), wastes time.
- Writing large files to home directory — hits 50 GB quota.
- Not checking stderr — missing critical error information.
- Retrying failed jobs blindly without investigating — wastes allocation.

## See Also

- [Agent Safety Guidelines](safety.md) — Security and destructive operation guidelines
- [Aurora System Overview](../systems/aurora/overview.md) — Aurora system constraints
- [Polaris System Overview](../systems/polaris/overview.md) — Polaris system constraints
