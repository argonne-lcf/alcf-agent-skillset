---
title: "Aurora System Overview"
category: systems
systems:
  - aurora
tags:
  - aurora
  - hardware
  - architecture
  - slingshot
  - intel-gpu
description: >
  Covers Aurora's node architecture (10,624 nodes, Intel Data Center GPU Max),
  Slingshot-11 interconnect, storage mounts, login nodes, and queue definitions.
  Load before any Aurora-specific task.
last_verified: "2026-04"
alcf_docs_url: "https://docs.alcf.anl.gov/aurora/getting-started/"
---

## Purpose

System overview for agents planning work on Aurora. Provides hardware specs, queue limits, storage paths, and operational constraints needed before submitting jobs or building software.

## Prerequisites

- ALCF account with active Aurora allocation.
- SSH access via `aurora.alcf.anl.gov`.

## Key Facts

- 10,624 compute nodes across 166 racks.
- Per node: 2x Intel Xeon CPU Max Series (Sapphire Rapids, 52 cores each = 104 cores per node), 6x Intel Data Center GPU Max Series (Ponte Vecchio, 2 tiles each = 12 GPU tiles per node).
- Memory per node: 128 GiB GPU HBM per GPU (768 GiB total GPU memory), 512 GiB DDR5 per CPU (1 TiB total).
- Cores 0 and 52 reserved for system services since March 2025 — applications should not bind to these.
- 8x HPE Slingshot-11 NICs per node, dragonfly topology.
- Storage mounts:
  - `/home` — 50 GB quota, backed up, available on login and compute.
  - `/lus/flare/projects` — Lustre parallel filesystem, 1 TB default project quota, primary stable storage.
  - DAOS — scratch object store embedded in Slingshot fabric, much faster than Lustre but NOT stable (data may be removed at any time).
  - `/opt/aurora` — read-only squashfs Aurora Programming Environment.
  - `/soft` — NFS, additional software; can cause scaling issues at large node counts (>1000).
  - `/soft/modulefiles` — additional module files (add with `module use /soft/modulefiles`).
- Login: `ssh <user>@aurora.alcf.anl.gov` (load-balanced to available UANs). Individual UANs named `aurora-uan-XXXX`.
- No GPUs on login nodes — must request compute allocation for GPU work.
- Proxy (required on compute nodes): `http://proxy.alcf.anl.gov:3128` — set `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`, `https_proxy`.
- Queue definitions:

| Queue | Nodes | Walltime | Notes |
|-------|-------|----------|-------|
| debug | 1-2 | 5min-1hr | Max 1 job/user, non-exclusive nodes |
| debug-scaling | 2-256 | 5min-1hr | Max 1 job/user |
| prod (routes to small/medium/large) | 256-10,624 | 5min-24hr | small: 256-1024/12h, medium: 1025-1919/18h, large: 1920-10624/24h |
| capacity | 1-16 | 5min-7d | Max 128 nodes total, max 5 queued, max 2 running |

- Global queue limits: 10 jobs running/accruing per project, 100 queued.
- Job submission requires filesystem flag: `-l filesystems=flare` or `-l filesystems=daos_user`.
- Do NOT submit jobs from `/soft/modulefiles` — jobs will terminate abruptly.
- Node failures are common in early production — checkpoint every 15-60 minutes.

## Examples

```bash
# SSH login
ssh username@aurora.alcf.anl.gov

# Basic job submission
qsub -A myproject -q debug -l select=1 -l walltime=00:30:00 -l filesystems=flare job.sh

# Interactive session
qsub -I -A myproject -q debug -l select=1 -l walltime=01:00:00 -l filesystems=flare

# Module commands
module use /soft/modulefiles
module avail
module load <module_name>

# Check queue status
qstat -u $USER
```

## Common Pitfalls

- Do not run compute-intensive work on login nodes — they are shared.
- Do not submit jobs from `/soft/modulefiles` directory.
- `/soft` (NFS) causes performance degradation at large scale — prefer `/opt/aurora` software.
- DAOS is NOT stable for long-term storage — can crash on large jobs with data loss.
- Node failures are frequent — always implement checkpointing.
- Applications dynamically loading libraries from Lustre at scale may trigger node crashes.

## See Also

- `../containers/` — Container skills for Aurora
- https://docs.alcf.anl.gov/aurora/getting-started/ — Official Aurora documentation
- https://docs.alcf.anl.gov/aurora/running-jobs-aurora/ — Aurora job submission details
