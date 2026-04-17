---
title: "Agent Safety Guidelines"
category: agents
systems:
  - all
tags:
  - agents
  - safety
  - security
  - credentials
description: >
  Security and safety rules for AI agents operating on ALCF systems. Covers
  credential handling, destructive operations, shared filesystem safety, and
  when to escalate to a human. Load at the start of any ALCF session.
last_verified: "2026-04"
---

## Purpose

Protect ALCF systems, user data, and project allocations from accidental damage by AI agents. These rules define hard boundaries that agents must not cross.

## Prerequisites

None — load alongside `etiquette.md` at the start of any ALCF session.

## Key Facts

### Credential Security

- NEVER store credentials, API keys, or tokens in job scripts or files on shared filesystems.
- NEVER echo or print credentials to stdout/stderr — job output files are stored in shared directories and may be readable by others.
- Use environment variables or secured config files (`~/.amsc/credentials.json` is managed by amsc-client).
- When writing job scripts via IRI base64 pattern, ensure no credentials are embedded in the script content.

### Destructive Operations

- Before `rm` or `rmdir` on shared filesystems: verify the path is correct and points to your own files.
- NEVER use `rm -rf` on directories you didn't create.
- NEVER delete from `/soft`, `/opt`, `/opt/aurora`, or system directories.
- NEVER modify system files, module files, or shared software installations.
- NEVER change permissions on shared directories or other users' files.
- When uncertain about a destructive operation: STOP and ask the human operator.

### Filesystem Safety

- Before large writes: check quota (`lfs quota`), verify destination path exists, confirm available space.
- Be aware that Eagle (`/eagle`) is NOT backed up — deletion is permanent.
- DAOS (Aurora) is scratch — data can disappear at any time.
- `/local/scratch` on Polaris is wiped between jobs.

### Allocation Protection

- ALCF allocations are finite and valuable — each node-hour spent is a project resource.
- Check project balance before submitting large jobs (use `sbank` commands if available).
- Start with small test jobs before scaling up.
- Do not retry failed jobs without investigating the failure first.

### Escalation Rules

- If a job produces unexpected output or errors you don't understand: report to the human.
- If you're unsure whether an operation is safe: ask first, act second.
- If a system seems to be behaving abnormally: stop and report.
- Never assume silence means success — always verify job completion and output.

## Examples

```python
# WRONG — credentials in job script
SCRIPT = f"""
export API_KEY={secret_key}
python my_app.py
"""

# RIGHT — credentials via environment, never in script
SCRIPT = """
python my_app.py  # reads API_KEY from ~/.config/myapp/config
"""
```

```bash
# WRONG — dangerous rm pattern
rm -rf $WORKDIR/  # if WORKDIR is unset, this becomes rm -rf /

# RIGHT — verify path first
if [ -d "$WORKDIR" ] && [ "$WORKDIR" != "/" ]; then
    rm -rf "$WORKDIR"
fi
```

## Common Pitfalls

- Hardcoding Globus tokens in Python scripts committed to shared filesystems.
- Using `rm -rf` in job cleanup with variable paths that could expand incorrectly (or be empty).
- Submitting expensive multi-node jobs without first testing on a single node.
- Retrying failed jobs in a loop without investigating — burns allocation.
- Assuming `exit_code == 0` means the job produced correct results.

## See Also

- [Agent Etiquette on ALCF Systems](etiquette.md) — Operational etiquette and courtesy rules
- [IRI API Fundamentals](../iri/api-fundamentals.md) — IRI API credential handling
- [Aurora System Overview](../systems/aurora/overview.md) — Aurora-specific constraints
- [Polaris System Overview](../systems/polaris/overview.md) — Polaris-specific constraints
