---
title: "Crux System Overview"
category: systems
systems:
  - crux
tags:
  - crux
  - hardware
  - architecture
  - slingshot
  - amd-epyc
  - cpu-only
description: >
  Covers Crux node architecture (256 nodes, 2x AMD EPYC Rome 64-core CPUs,
  CPU-only), Slingshot interconnect, storage mounts, login nodes, and queue
  definitions. Load before any Crux-specific task.
last_verified: "2026-06"
alcf_docs_url: "https://docs.alcf.anl.gov/crux/queueing-and-running-jobs/running-jobs/"
---

## Purpose

System overview for agents planning work on Crux. Provides hardware specs, queue limits, storage paths, and operational constraints needed before submitting jobs or building software. Crux is the CPU-only HPE Cray EX system at ALCF, intended for data-analytics, pre/post-processing, and CPU workloads adjacent to Polaris/Aurora.

## Prerequisites

- ALCF account with active Crux allocation.
- SSH access via `crux.alcf.anl.gov`.

## Key Facts

- HPE Cray EX Liquid Cooled system, peak performance 1.18 PF, **CPU-only** (no GPUs).
- 256 compute nodes total (64 compute blades × 4 nodes/blade).
- Per compute node: 2x AMD EPYC 7742 (Rome) 64-core CPUs = 128 physical cores, 256 hyperthreads. 256 GB DDR4 (128 GB per CPU).
- Each CPU has 4 NUMA domains × 16 cores. For NUMA-aware binding, see node architecture in the Crux machine-overview docs.
- User Access Nodes (UANs / login nodes): `crux-login-01`, `crux-login-02` — dual-socket AMD EPYC 7543 (Milan) 32-core.
- Interconnect: HPE Slingshot.
- Storage mounts:
  - `/home` — small home directory with quota; backed up.
  - `/eagle` (`/lus/eagle/projects`) — project storage on Eagle, shared with Polaris; NOT backed up. Mount on a job with `-l filesystems=home:eagle`.
  - `/lus/grand/projects` — Grand project storage, also available depending on allocation.
  - Lustre file striping applies — see ALCF training material for tuning large I/O.
- Module system: `module use /soft/modulefiles` for additional software (e.g. `module load spack-pe-base; module load cmake`).
- Proxy (required on compute nodes for outbound HTTP): `http://proxy.alcf.anl.gov:3128` — set `HTTP_PROXY`/`HTTPS_PROXY`/`http_proxy`/`https_proxy`/`ftp_proxy`.
- Default `OMP_NUM_THREADS` on a compute node is 256 (all hyperthreads). **Set it explicitly** for OpenMP codes or risk severe oversubscription.
- Queue definitions:

| Queue | Nodes | Walltime | Notes |
|-------|-------|----------|-------|
| debug | 1-8 | 5min-2hr | 8-node jobs are exclusive |
| workq-route → workq | 1-184 | 5min-24hr | Routing queue. workq: 20 jobs queued/running per project, 10 running |
| preemptable | 1-10 | 5min-72hr | Killable without warning when demand jobs arrive. Max 20 jobs running/accruing/queued per project. Use `#PBS -r y` to make jobs rerunnable |
| demand | 1-64 | 5min-1hr | By request only — email support@alcf.anl.gov |

- `workq-route` is the routing queue that lands jobs in the `workq` execution queue (cap: 184 nodes, 24 hr).
- Per-project limit on `workq-route`: 100 jobs max.
- Job submission requires the `select=N:system=crux` resource string and a `filesystems` flag (e.g. `-l filesystems=home:eagle`).
- `place=scatter` distributes ranks across nodes; common for MPI jobs.

## Examples

```bash
# SSH login
ssh username@crux.alcf.anl.gov

# Interactive 1-node debug session
qsub -I -A myproject -q debug -l select=1:system=crux \
  -l walltime=00:30:00 -l filesystems=home:eagle

# Submit an MPI+OpenMP batch job (4 nodes, 8 ranks/node, 8 OMP threads/rank)
qsub job.sh

# Inspect queue
qstat -u $USER
qstat -Qf workq

# Module commands
module use /soft/modulefiles
module avail
module load spack-pe-base
module load cmake
```

Sample PBS submission script (MPI+OpenMP, 4 nodes, 64 ranks/node × 2 OMP threads):

```bash
#!/bin/bash -l
#PBS -N AFFINITY
#PBS -l select=4:system=crux
#PBS -l place=scatter
#PBS -l walltime=0:10:00
#PBS -q debug
#PBS -A myproject
#PBS -l filesystems=home:eagle

NNODES=$(wc -l < $PBS_NODEFILE)
NRANKS_PER_NODE=64
NDEPTH=2
NTHREADS=2
NTOTRANKS=$(( NNODES * NRANKS_PER_NODE ))

cd $PBS_O_WORKDIR

MPI_ARGS="-n ${NTOTRANKS} --ppn ${NRANKS_PER_NODE} --depth=${NDEPTH} --cpu-bind depth"
OMP_ARGS="--env OMP_NUM_THREADS=${NTHREADS} --env OMP_PROC_BIND=true --env OMP_PLACES=cores"

mpiexec ${MPI_ARGS} ${OMP_ARGS} ./hello_affinity
```

Useful `mpiexec` flags on Crux:
- `-n <N>` total MPI ranks; `-ppn <N>` ranks per node.
- `--cpu-bind <type>` (`depth`, `list:0:1:...`, etc.) for explicit core pinning.
- `--depth <N>` hardware threads per rank (pair with `--cpu-bind depth`).
- `--env VAR=value` set environment variables for ranks.
- `--hostfile <file>` override the default `$PBS_NODEFILE` (needed when launching multiple MPI apps on disjoint node subsets).

## Common Pitfalls

- **No GPUs on Crux** — if a workload requires accelerators, target Polaris or Aurora instead.
- `select=N` alone is insufficient — include `system=crux` (`-l select=N:system=crux`) and a `filesystems` flag, otherwise jobs may be rejected or queue against the wrong resources.
- Default `OMP_NUM_THREADS=256` on compute nodes — always set it explicitly for OpenMP codes, otherwise threads will heavily oversubscribe the 128 physical cores.
- `preemptable` queue jobs can be killed at any moment when the `demand` queue is in use — add `#PBS -r y` if the job is rerunnable.
- The `demand` queue is by-request-only — do not target it without prior approval from support@alcf.anl.gov.
- Compute nodes have no direct internet — export the `proxy.alcf.anl.gov:3128` proxy variables before any outbound HTTP/HTTPS/FTP.
- `/eagle` is NOT backed up — archive critical data yourself.
- When launching multiple `mpiexec` instances on different node subsets, you must split `$PBS_NODEFILE` and pass `--hostfile` explicitly — without it, every invocation defaults to the full node list.

## See Also

- `../polaris/overview.md` — Polaris (GPU sibling system, also mounts `/eagle`)
- `../aurora/overview.md` — Aurora (Intel GPU system)
- `../../iri/job-submission.md` — submitting Crux jobs via the IRI API
- https://docs.alcf.anl.gov/crux/getting-started/ — Crux getting started
- https://docs.alcf.anl.gov/crux/queueing-and-running-jobs/running-jobs/ — Crux queues and job submission
- https://github.com/argonne-lcf/GettingStarted/tree/master/Examples/Crux — Crux example jobs (affinity, ensembles)
