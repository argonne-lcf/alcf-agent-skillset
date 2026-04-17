---
title: "PyTorch Distributed Training on Polaris"
category: software
systems:
  - polaris
tags:
  - pytorch
  - ddp
  - distributed-training
  - nccl
  - torchrun
  - polaris
  - gpu
description: >
  How to run multi-node PyTorch DDP training on Polaris using Apptainer containers
  with NCCL over Slingshot-11. Covers container strategy (no MPICH needed), torchrun
  launch pattern, NCCL configuration, and AWS OFI NCCL plugin setup. Load when
  setting up distributed PyTorch training on Polaris.
last_verified: "2026-04"
alcf_docs_url: "https://docs.alcf.anl.gov/polaris/data-science-workflows/frameworks/pytorch/"
---

## Purpose

Run multi-node distributed PyTorch training on Polaris using containers with NCCL communication over Slingshot-11.

## Prerequisites

- Docker locally (for building the container image).
- Polaris allocation.
- `amsc-client` if using IRI API.

## Key Facts

### Container Strategy (DIFFERENT from MPI container approach)

PyTorch DDP does NOT use MPICH inside the container. The architecture is fundamentally different from MPI-based container workloads:

- **No MPICH in the container.** Host `mpiexec` handles process launching only.
- **Container only needs PyTorch + torchrun.** No MPI libraries required.
- **Host `mpiexec` wraps `torchrun`** — one `torchrun` per node, each spawning 4 GPU workers.

| Component | Location | Reason |
|-----------|----------|--------|
| PyTorch + torchrun | Container | Training framework |
| Training script | Container (baked in or bind-mount) | Workload |
| mpiexec | Host | Process launcher |
| Cray MPICH ABI | Host | Slingshot driver |
| AWS OFI NCCL plugin | Host (bind-mount) | NCCL transport for Slingshot-11 |
| hwloc | Host (bind-mount) | Topology detection |

### Dockerfile

```dockerfile
FROM nvidia/cuda:12.6.3-devel-ubuntu24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev build-essential ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir torch==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124

WORKDIR /workspace
CMD ["/bin/bash"]
```

Note: PyTorch 2.5.1 for CUDA 12.4 works on Polaris (CUDA 12.6 driver). Forward compatible.

### Launch Pattern — CRITICAL (get -ppn right!)

```bash
mpiexec \
    -n ${NNODES} \
    -ppn 1 \
    --hostfile ${PBS_NODEFILE} \
    --depth=${NPROC_PER_NODE} \
    --cpu-bind depth \
    apptainer exec \
        -B /opt -B /soft -B /var/run/palsd/ \
        -B /usr/lib64:/host/usr/lib64 \
        -B ${OFI_NCCL_LIB}:/ofi-nccl \
        --nv --writable-tmpfs --fakeroot \
        ${SIF} \
    torchrun \
        --nnodes=${NNODES} \
        --nproc_per_node=${NPROC_PER_NODE} \
        --rdzv_backend=c10d \
        --rdzv_endpoint=${HEAD_NODE}:29500 \
        /workspace/train_ddp.py
```

Key differences from MPI launch:

- **`-ppn 1`** — ONE torchrun process per node. Each torchrun spawns `NPROC_PER_NODE` (4) GPU workers internally.
- **`-n ${NNODES}`** — Total mpiexec ranks = number of nodes, NOT number of GPUs.
- **`--depth` and `--cpu-bind depth`** — CPU affinity for GPU workers.

### NCCL Configuration for Slingshot-11 (ALL required)

```bash
export APPTAINERENV_LD_PRELOAD="/ofi-nccl/libnccl-net.so"
export APPTAINERENV_NCCL_NET="AWS Libfabric"
export APPTAINERENV_NCCL_NET_GDR_LEVEL=PHB
export APPTAINERENV_NCCL_CROSS_NIC=1
export APPTAINERENV_NCCL_COLLNET_ENABLE=1
export APPTAINERENV_FI_CXI_DISABLE_HOST_REGISTER=1
export APPTAINERENV_FI_MR_CACHE_MONITOR=userfaultfd
export APPTAINERENV_FI_CXI_DEFAULT_CQ_SIZE=131072
```

**Critical:** `LD_PRELOAD` is MANDATORY for the NCCL plugin. `LD_LIBRARY_PATH` alone is NOT sufficient. NCCL will not auto-discover the plugin — you must preload it.

### LD_LIBRARY_PATH (must include hwloc!)

```bash
export APPTAINERENV_LD_LIBRARY_PATH="${CRAY_LD_LIBRARY_PATH}:${LD_LIBRARY_PATH}:/opt/cray/pe/pals/1.2.12/lib:/host/usr/lib64:/ofi-nccl:/soft/libraries/hwloc/lib"
```

### OFI NCCL Plugin Location

The AWS OFI NCCL plugin is at: `/soft/libraries/aws-ofi-nccl/v1.9.1-aws/lib`

Set this as:
```bash
OFI_NCCL_LIB=/soft/libraries/aws-ofi-nccl/v1.9.1-aws/lib
```

### Bind Mounts (additional vs MPI containers)

In addition to the standard bind mounts (`/opt`, `/var/run/palsd/`, `/usr/lib64:/host/usr/lib64`), PyTorch DDP requires:

- `-B /soft` — ALCF software stack including hwloc
- `-B ${OFI_NCCL_LIB}:/ofi-nccl` — AWS OFI NCCL plugin for Slingshot

### Module Load Sequence

Same as MPI containers:

```bash
module use /soft/modulefiles
module load spack-pe-base apptainer cray-mpich-abi
```

## Examples

### Minimal DDP Training Script (train_ddp.py)

```python
import os, time, socket, torch, torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader, DistributedSampler

def setup():
    dist.init_process_group(backend="nccl")
    torch.cuda.set_device(int(os.environ["LOCAL_RANK"]))

def train():
    setup()
    rank = dist.get_rank()
    local_rank = int(os.environ["LOCAL_RANK"])
    device = torch.device(f"cuda:{local_rank}")

    # Model + DDP
    model = MyModel().to(device)
    model = DDP(model, device_ids=[local_rank])

    # Training loop with DistributedSampler
    dataset = MyDataset()
    sampler = DistributedSampler(dataset, shuffle=True)
    loader = DataLoader(dataset, batch_size=8, sampler=sampler)

    for batch in loader:
        # forward, backward, step...
        pass

    dist.destroy_process_group()

if __name__ == "__main__":
    train()
```

### Complete PBS Job Script

```bash
#!/bin/bash -l
#PBS -l select=2:system=polaris
#PBS -l walltime=00:30:00
#PBS -l filesystems=home:eagle
#PBS -q debug
#PBS -A <your_project>
set -e

# --- Modules ---
module use /soft/modulefiles
module load spack-pe-base apptainer cray-mpich-abi

# --- Apptainer env ---
export APPTAINER_TMPDIR=/local/scratch/apptainer-tmpdir
export APPTAINER_CACHEDIR=/local/scratch/apptainer-cachedir
mkdir -p $APPTAINER_TMPDIR $APPTAINER_CACHEDIR

# --- Proxy (needed for any network access) ---
export HTTP_PROXY=http://proxy.alcf.anl.gov:3128
export HTTPS_PROXY=http://proxy.alcf.anl.gov:3128
export http_proxy=http://proxy.alcf.anl.gov:3128
export https_proxy=http://proxy.alcf.anl.gov:3128

# --- Node topology ---
NNODES=$(cat $PBS_NODEFILE | wc -l)
NPROC_PER_NODE=4
HEAD_NODE=$(head -1 $PBS_NODEFILE)

# --- Container ---
SIF=$HOME/pytorch-ddp/pytorch-ddp.sif
OFI_NCCL_LIB=/soft/libraries/aws-ofi-nccl/v1.9.1-aws/lib

# --- NCCL configuration for Slingshot-11 ---
export APPTAINERENV_LD_PRELOAD="/ofi-nccl/libnccl-net.so"
export APPTAINERENV_NCCL_NET="AWS Libfabric"
export APPTAINERENV_NCCL_NET_GDR_LEVEL=PHB
export APPTAINERENV_NCCL_CROSS_NIC=1
export APPTAINERENV_NCCL_COLLNET_ENABLE=1
export APPTAINERENV_FI_CXI_DISABLE_HOST_REGISTER=1
export APPTAINERENV_FI_MR_CACHE_MONITOR=userfaultfd
export APPTAINERENV_FI_CXI_DEFAULT_CQ_SIZE=131072

# --- LD_LIBRARY_PATH (must include hwloc!) ---
export APPTAINERENV_LD_LIBRARY_PATH="${CRAY_LD_LIBRARY_PATH}:${LD_LIBRARY_PATH}:/opt/cray/pe/pals/1.2.12/lib:/host/usr/lib64:/ofi-nccl:/soft/libraries/hwloc/lib"

# --- Launch: one torchrun per node, each spawning 4 GPU workers ---
mpiexec \
    -n ${NNODES} \
    -ppn 1 \
    --hostfile ${PBS_NODEFILE} \
    --depth=${NPROC_PER_NODE} \
    --cpu-bind depth \
    apptainer exec \
        -B /opt -B /soft -B /var/run/palsd/ \
        -B /usr/lib64:/host/usr/lib64 \
        -B ${OFI_NCCL_LIB}:/ofi-nccl \
        --nv --writable-tmpfs --fakeroot \
        ${SIF} \
    torchrun \
        --nnodes=${NNODES} \
        --nproc_per_node=${NPROC_PER_NODE} \
        --rdzv_backend=c10d \
        --rdzv_endpoint=${HEAD_NODE}:29500 \
        /workspace/train_ddp.py
```

### Expected Output

```
=== Toy DDP Transformer ===
World size : 8
Device     : NVIDIA A100-SXM4-40GB
Tokens/sec : ~383K (2 nodes, 8 GPUs)
Tokens/sec/GPU : ~47.9K
Near-linear scaling observed.
```

## Common Pitfalls

- **`NCCL WARN Error: network AWS Libfabric not found`** — `LD_PRELOAD` not set. Must preload `/ofi-nccl/libnccl-net.so`.
- **`libhwloc.so.0: cannot open`** — Missing `-B /soft` bind mount and `/soft/libraries/hwloc/lib` in `LD_LIBRARY_PATH`.
- **Rank mismatch / duplicate ranks** — Using `-ppn 4` with mpiexec (WRONG). Use `-ppn 1` — one torchrun per node spawns 4 workers internally. `-n 8 -ppn 4` creates 8x4=32 ranks!
- **Hangs at `init_process_group`** — NCCL cannot communicate. Check `NCCL_DEBUG=INFO`, verify `-B /opt`.
- **`duration` is seconds in IRI API** (not minutes).
- **Debug queue:** max 1 job, need 30-60s buffer between sequential submits.

## See Also

- `../containers/polaris-container-run.md` — MPI container runtime (different approach)
- `../containers/polaris-container-build.md` — Container building basics
- `../iri/job-submission.md` — Submitting via IRI API
- `../systems/polaris/overview.md` — Polaris system overview
- https://docs.alcf.anl.gov/polaris/data-science-workflows/frameworks/pytorch/
