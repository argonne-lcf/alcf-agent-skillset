---
title: "Building Containers for Polaris"
category: containers
systems:
  - polaris
tags:
  - containers
  - apptainer
  - docker
  - mpich
  - polaris
  - build
description: >
  How to build Docker containers targeting Polaris hardware (NVIDIA A100, Cray MPICH ABI).
  Covers Dockerfile requirements, MPICH version matching, glibc constraints, and container
  pull with Apptainer. Load when building a container for Polaris compute nodes.
last_verified: "2026-04"
alcf_docs_url: "https://docs.alcf.anl.gov/polaris/containers/"
---

## Purpose

Guide for building Docker containers that work with Polaris's Cray MPICH ABI hybrid mode. Containers are built locally with Docker, pushed to a registry, then pulled and converted to SIF format on Polaris with Apptainer.

## Prerequisites

- Docker installed locally.
- Docker Hub (or other registry) account.
- Polaris allocation.

## Key Facts

Non-negotiable container requirements:

| Requirement | Why |
|-------------|-----|
| Base image: Ubuntu 24.04+ | glibc >= 2.38 required by Cray libfabric 2.2.0rc1 |
| Install to `/usr/local` | Apptainer `-B /opt` bind-mount overwrites container's `/opt` at runtime |
| MPICH 4.1.2 from source | Must match Cray MPICH 9.0.1 (which is ANL MPICH 4.1.2 base) |
| `--with-device=ch4:ofi` | Required for Slingshot network; `ch4:ucx` (apt default) won't work cross-node |
| Do NOT install `libfabric-dev` | Causes linker errors for psm2/rdmacm/ibverbs/efa providers; MPICH uses embedded OFI |
| `-fno-lto` build flags | LTO + CUDA fatbinData symbol collision |

- At time of writing: Cray MPICH 9.0.1 = ANL MPICH base 4.1.2.
- To verify the MPICH version on Polaris, submit a probe job running:
  ```bash
  /opt/cray/pe/mpich/9.0.1/ofi/cray/20.0/bin/mpichversion
  ```

## Examples

Complete working Dockerfile:

```dockerfile
FROM nvidia/cuda:12.6.3-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git wget ca-certificates \
    pkg-config python3 python3-dev libjson-c-dev gfortran \
    && rm -rf /var/lib/apt/lists/*

# Build MPICH 4.1.2 from source with ch4:ofi
WORKDIR /build/mpich
RUN wget -q https://www.mpich.org/static/downloads/4.1.2/mpich-4.1.2.tar.gz \
    && tar xzf mpich-4.1.2.tar.gz \
    && cd mpich-4.1.2 \
    && ./configure \
        --prefix=/usr/local \
        --with-device=ch4:ofi \
        --disable-wrapper-rpath \
        --enable-shared \
        FFLAGS='-O3 -fallow-argument-mismatch' \
        FCFLAGS='-O3 -fallow-argument-mismatch' \
        CFLAGS='-O3' CXXFLAGS='-O3' \
    && make -j$(nproc) && make install && ldconfig \
    && cd / && rm -rf /build/mpich

# Build your application to /usr/local (NOT /opt)
# Use -fno-lto for GPU apps

# Add MPI diagnostic binary
RUN printf '#include <stdio.h>\n#include <mpi.h>\n#include <limits.h>\n#include <unistd.h>\nint main(int argc, char** argv) {\n    MPI_Init(&argc, &argv);\n    int rank, size;\n    MPI_Comm_rank(MPI_COMM_WORLD, &rank);\n    MPI_Comm_size(MPI_COMM_WORLD, &size);\n    char host[HOST_NAME_MAX];\n    gethostname(host, HOST_NAME_MAX);\n    printf("MPI rank %%d of %%d on %%s\\n", rank, size, host);\n    MPI_Finalize();\n    return 0;\n}\n' > /tmp/mpi_hello.c \
    && mpicc -o /usr/local/bin/mpi_hello /tmp/mpi_hello.c \
    && rm /tmp/mpi_hello.c

WORKDIR /work
```

Pulling and converting the container on Polaris:

```bash
# Set proxy (required on Polaris compute nodes)
export HTTP_PROXY=http://proxy.alcf.anl.gov:3128
export HTTPS_PROXY=http://proxy.alcf.anl.gov:3128

# Use local NVMe for Apptainer scratch
export APPTAINER_TMPDIR=/local/scratch/apptainer-tmpdir
export APPTAINER_CACHEDIR=/local/scratch/apptainer-cachedir
mkdir -p $APPTAINER_TMPDIR $APPTAINER_CACHEDIR

# Pull and convert to SIF (use versioned filename!)
apptainer pull /home/$USER/my-app-v4.sif docker://docker.io/myuser/my-app:v4
```

## Common Pitfalls

- glibc 2.35 (Ubuntu 22.04) too old: SIGABRT crash from Cray libfabric. Use Ubuntu 24.04+.
- Installing `libfabric-dev` via apt: linker errors for psm2/rdmacm providers. MPICH bundles OFI internally.
- Using apt MPICH (`ch4:ucx`): works on single node but fails cross-node. Build from source with `ch4:ofi`.
- Installing to `/opt`: overwritten by `-B /opt` bind mount at runtime. Use `/usr/local`.
- Docker tag caching: after pushing `:latest`, old SIF may be cached on Polaris. Always use versioned SIF filenames.
- MPICH version mismatch (e.g., 3.4.3 vs host 4.1.2): MPI collectives crash but `mpi_hello` may still pass.

## See Also

- `polaris-container-run.md` — Running containers on Polaris
- `../iri/job-submission.md` — Submitting container jobs via IRI
- https://docs.alcf.anl.gov/polaris/containers/ — Official container docs
