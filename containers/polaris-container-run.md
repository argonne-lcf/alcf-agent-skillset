---
title: "Running Containers on Polaris"
category: containers
systems:
  - polaris
tags:
  - containers
  - apptainer
  - mpi
  - polaris
  - runtime
  - bind-mounts
description: >
  How to run Apptainer containers on Polaris compute nodes with MPI, GPU access,
  and Cray MPICH ABI override. Covers bind mounts, LD_LIBRARY_PATH, CMA fix,
  and mpiexec flags. Load when executing containerized workloads on Polaris.
last_verified: "2026-04"
alcf_docs_url: "https://docs.alcf.anl.gov/polaris/containers/"
---

## Purpose

Runtime configuration for executing containerized MPI+GPU workloads on Polaris using Apptainer with Cray MPICH ABI override. Every flag and environment variable documented here was discovered through iterative debugging.

## Prerequisites

- Container image built per `polaris-container-build.md`.
- SIF file on Polaris.
- Active job allocation.

## Key Facts

Module load sequence (order matters):

```bash
module use /soft/modulefiles
module load spack-pe-base apptainer cray-mpich-abi
```

`spack-pe-base` must come first. Lmod will say "cray-mpich -> cray-mpich-abi" -- this is expected.

LD_LIBRARY_PATH assembly:

```bash
export APPTAINERENV_LD_LIBRARY_PATH="\
$CRAY_LD_LIBRARY_PATH:\
$LD_LIBRARY_PATH:\
/opt/cray/pe/pals/1.2.12/lib:\
/host/usr/lib64"
```

CMA (Cross-Memory Attach) fix -- CRITICAL:

```bash
export APPTAINERENV_MPICH_SMP_SINGLE_COPY_MODE=NONE
```

Without this, MPI collectives (`MPI_Reduce`, `MPI_Allreduce`, `MPI_Bcast`) crash with "CMA does not have sufficient permission". `FI_CXI_DISABLE_CMA=1` and `MPICH_SHM_DISABLE_CMA=1` do NOT work.

MPICH ABI compatibility chain:

```
Container MPICH 4.1.2 (ch4:ofi)
    | ABI override at runtime
Cray MPICH 9.0.1 (ANL MPICH base 4.1.2)
    |
HPE Cray Slingshot (libfabric + libcxi)
    |
Physical HSN
```

Bind mount table:

| Bind Mount | What's Inside | Why Needed |
|------------|---------------|------------|
| `-B /opt` | Cray PE, libfabric, MPICH, CUDA | Host MPI and fabric runtime |
| `-B /var/run/palsd/` | PALS daemon Unix socket | MPI job launcher |
| `-B /usr/lib64:/host/usr/lib64` | libcxi.so.1 | Cray Slingshot fabric library |
| `-B $HOME:$HOME` | User's home directory | Output files, SIF, run dir |

Note: `/usr/lib64` mounted to `/host/usr/lib64` to avoid overwriting container's own `/usr/lib64`.

Critical apptainer exec flags:

| Flag | Why |
|------|-----|
| `--fakeroot` | Required for apptainer exec in this config |
| `--nv` | Expose NVIDIA GPU and CUDA to container |
| `--writable-tmpfs` | App cache writes fail without this |
| `-B /opt` | Bind-mounts host Cray libs |
| `--pwd $RUNDIR` | Use clean writable dir to avoid stale configs |

## Examples

Complete job script template:

```bash
#!/bin/bash -l
set -e

module use /soft/modulefiles
module load spack-pe-base apptainer cray-mpich-abi

export APPTAINER_TMPDIR=/local/scratch/apptainer-tmpdir
export APPTAINER_CACHEDIR=/local/scratch/apptainer-cachedir
mkdir -p $APPTAINER_TMPDIR $APPTAINER_CACHEDIR

export HTTP_PROXY=http://proxy.alcf.anl.gov:3128
export HTTPS_PROXY=http://proxy.alcf.anl.gov:3128
export http_proxy=http://proxy.alcf.anl.gov:3128
export https_proxy=http://proxy.alcf.anl.gov:3128

export APPTAINERENV_LD_LIBRARY_PATH="$CRAY_LD_LIBRARY_PATH:$LD_LIBRARY_PATH:/opt/cray/pe/pals/1.2.12/lib:/host/usr/lib64"
export APPTAINERENV_MPICH_SMP_SINGLE_COPY_MODE=NONE

SIF=$HOME/my-app/my-app-v4.sif
RUNDIR=$HOME/my-app/run
mkdir -p $RUNDIR

NODES=$(cat $PBS_NODEFILE | wc -l)
RANKS_PER_NODE=4
RANKS=$((NODES * RANKS_PER_NODE))

mpiexec -n $RANKS -ppn $RANKS_PER_NODE --hostfile $PBS_NODEFILE \
    apptainer exec --fakeroot --nv --writable-tmpfs \
    -B /opt -B /var/run/palsd/ \
    -B /usr/lib64:/host/usr/lib64 \
    -B $HOME:$HOME \
    --pwd $RUNDIR \
    "$SIF" \
    my-app --my-args
```

Verification with mpi_hello:

```bash
echo "=== mpi_hello verification ==="
mpiexec -n $RANKS -ppn $RANKS_PER_NODE --hostfile $PBS_NODEFILE \
    apptainer exec --fakeroot --nv --writable-tmpfs \
    -B /opt -B /var/run/palsd/ \
    -B /usr/lib64:/host/usr/lib64 \
    "$SIF" mpi_hello
```

Expected output (2 nodes, 4 ranks/node = 8 total):

```
MPI rank 0 of 8 on x3210c0s25b0n0
MPI rank 1 of 8 on x3210c0s25b0n0
...
MPI rank 4 of 8 on x3210c0s37b1n0
...
```

Two distinct hostnames confirms cross-node MPI. Same hostname = broken multi-node (likely MPICH version mismatch).

IMPORTANT: `mpi_hello` passing does NOT guarantee collectives work. You need an `MPI_Reduce` test to confirm the CMA fix is working.

## Common Pitfalls

- `module: command not found`: script not running as login shell. Use `#!/bin/bash -l`.
- `executable not found in $PATH`: container `/opt` was bind-overwritten. Install to `/usr/local`.
- `libcuda.so.1: cannot open`: add `--nv` flag.
- `libcxi.so.1: cannot open`: add `-B /usr/lib64:/host/usr/lib64` and `/host/usr/lib64` to LD_LIBRARY_PATH.
- `read-only file system`: add `--writable-tmpfs`.
- `CMA does not have sufficient permission`: set `APPTAINERENV_MPICH_SMP_SINGLE_COPY_MODE=NONE`.
- MPI collective crash (`MPI_Reduce`): MPICH version mismatch, rebuild container with 4.1.2.

## See Also

- `polaris-container-build.md` — Building containers for Polaris
- `../software/frameworks/pytorch-ddp-polaris.md` — PyTorch DDP (uses different container strategy)
- `../iri/job-submission.md` — Submitting jobs via IRI API
