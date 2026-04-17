---
title: "Polaris System Overview"
category: systems
systems:
  - polaris
tags:
  - polaris
  - hardware
  - architecture
  - slingshot
  - nvidia-gpu
  - a100
description: >
  Covers Polaris node architecture (560 nodes, 4x A100 GPUs), Slingshot-11
  interconnect, storage mounts, login nodes, and queue definitions. Load before
  any Polaris-specific task.
last_verified: "2026-04"
alcf_docs_url: "https://docs.alcf.anl.gov/polaris/getting-started/"
---

## Purpose

System overview for agents planning work on Polaris. Provides hardware specs, queue limits, storage paths, and operational constraints.

## Prerequisites

- ALCF account with active Polaris allocation.
- SSH access via `polaris.alcf.anl.gov`.

## Key Facts

- 560 HPE Apollo Gen10+ compute nodes across 40 racks.
- Per node: 1x AMD EPYC Milan 7543P (32 cores / 64 threads), 4x NVIDIA A100 40GB GPUs (connected via NVLink, 600 GB/s per pair), 512 GiB DDR4.
- Local NVMe SSD: 2x 1.6 TB (RAID0 = 3.2 TB at `/local/scratch`) — wiped between jobs.
- 2x HPE Slingshot-11 NICs per node (200 Gbps each).
- 4 login nodes: `polaris-login-{01..04}.hsn.cm.polaris.alcf.anl.gov` — NO GPUs on login nodes.
- Storage mounts:
  - `/home` or `/lus/agile/home` — 50 GB quota, backed up.
  - `/eagle` or `/lus/eagle/projects` — project storage, NOT backed up, user responsible for archival.
  - `/local/scratch` — local NVMe, per-job only, wiped between jobs.
- Proxy (required on compute nodes): `http://proxy.alcf.anl.gov:3128`.
- Module system: `module use /soft/modulefiles` to access additional software.
- Queue definitions:

| Queue | Nodes | Walltime | Notes |
|-------|-------|----------|-------|
| debug | 1-2 | 5min-1hr | Max 1 job/user |
| debug-scaling | 1-10 | 5min-1hr | Max 1 job/user |
| prod (routes to small/medium/large) | 10-496 | 5min-24hr | small: 10-24/3h, medium: 25-99/6h, large: 100-496/24h |
| preemptable | 1-10 | 5min-72hr | Can be killed without warning by demand queue; use `-r y` for rerunnable |
| capacity | 1-4 | 5min-7d | Max 32 nodes total, max 2 queued, max 1 running |

- Global limits: 10 jobs running/accruing per project, 100 queued.
- Recommended max job size: 476-486 nodes (larger may queue indefinitely due to downed nodes).
- GPU builds require a compute node allocation — no GPUs on login nodes.

## Examples

```bash
# SSH login
ssh username@polaris.alcf.anl.gov

# Interactive session with GPU
qsub -I -l select=1 -l filesystems=home:eagle -l walltime=1:00:00 -q debug -A myproject

# Basic job submission
qsub -A myproject -q debug -l select=2 -l walltime=00:30:00 -l filesystems=home:eagle job.sh

# Check queue
qstat -u $USER

# Module commands
module use /soft/modulefiles
module avail
module load conda
```

## Common Pitfalls

- No GPUs on login nodes — GPU builds must use compute allocation.
- Eagle filesystem is NOT backed up — archive critical data yourself.
- Preemptable queue jobs can be killed instantly without warning.
- Avoid requesting >486 nodes — may queue indefinitely.
- Login nodes are shared — no compute-intensive preprocessing.
- `/local/scratch` is wiped between jobs — do not rely on it for persistence.

## See Also

- `../containers/polaris-container-build.md` — Building containers for Polaris
- `../containers/polaris-container-run.md` — Running containers on Polaris
- `../software/frameworks/pytorch-ddp-polaris.md` — PyTorch DDP training
- https://docs.alcf.anl.gov/polaris/getting-started/ — Official Polaris documentation
